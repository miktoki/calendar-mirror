<script lang="ts">
	import type { CalendarEvent, WeatherRecord } from '$lib/api';
	import { eventColor } from '$lib/api';
	import {
		eventStart, eventEnd, isAllDay, formatTime, formatDate,
		eventsOnDay, addDays, startOfDay, localDateStr, layoutOverlappingTimedEvents
	} from '$lib/dateUtils';
	import WeatherWidget from './WeatherWidget.svelte';
	import { currentView } from '$lib/stores';
	import EventPopup from './EventPopup.svelte';

	export let events: CalendarEvent[];
	export let anchor: Date;
	export let weather: WeatherRecord | null = null;

	let popupEvent: CalendarEvent | null = null;

	$: day = startOfDay(anchor);
	$: dayEvents = eventsOnDay(events, day);
	$: timedEvents = dayEvents.filter((e) => !isAllDay(e));
	$: allDayEvents = dayEvents.filter((e) => isAllDay(e));
	$: layout = layoutOverlappingTimedEvents(timedEvents);

	const today = new Date();

	$: daySeries = (weather?.forecast?.properties?.timeseries ?? []).filter(
		(ts) => localDateStr(new Date(ts.time)) === localDateStr(day)
	);

	const HOUR_HEIGHT = 64;
	const START_HOUR = 6;
	const END_HOUR = 23;

	function topPx(ev: CalendarEvent): number {
		const s = eventStart(ev);
		const minutes = s.getHours() * 60 + s.getMinutes() - START_HOUR * 60;
		return Math.max(0, (minutes / 60) * HOUR_HEIGHT);
	}

	function heightPx(ev: CalendarEvent): number {
		const s = eventStart(ev);
		const e = eventEnd(ev);
		const dur = (e.getTime() - s.getTime()) / 60000;
		return Math.max(20, (dur / 60) * HOUR_HEIGHT);
	}

	const hours = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, i) => START_HOUR + i);

	$: isToday = day.toDateString() === today.toDateString();
</script>

<div class="day-view">
	<header class="day-header">
		<button class="outline nav-btn" on:click={() => (anchor = addDays(anchor, -1))}>‹</button>
		<h2 class="nav-label" on:click={() => currentView.set('week')}>{formatDate(day)}</h2>
		<div class="header-right">
			{#if !isToday}
				<button class="outline today-btn" on:click={() => (anchor = new Date())}>Today</button>
			{/if}
			<button class="outline nav-btn" on:click={() => (anchor = addDays(anchor, 1))}>›</button>
		</div>
	</header>

	{#if allDayEvents.length}
		<div class="allday-row">
			{#each allDayEvents as ev}
				{@const c = eventColor(ev)}
				<span class="chip" style="background: {c.bg}; color: {c.fg};" on:click={() => (popupEvent = ev)}>{ev.summary}</span>
			{/each}
		</div>
	{/if}

	<div class="scroll-area">
		<div class="time-grid" style="height: {(END_HOUR - START_HOUR + 1) * HOUR_HEIGHT}px">
			{#each hours as h}
				<div class="hour-row" style="top: {(h - START_HOUR) * HOUR_HEIGHT}px; height: {HOUR_HEIGHT}px">
					<span class="hour-label">{String(h).padStart(2, '0')}:00</span>
					{#if daySeries.length}
						<span class="hour-weather">
							<WeatherWidget series={daySeries} hour={h} />
						</span>
					{/if}
					<div class="hour-line"></div>
				</div>
			{/each}

			{#each timedEvents as ev}
				{@const c = eventColor(ev)}
				{@const h = heightPx(ev)}
				{@const compact = h < 32}
				{@const l = layout.get(ev.id)}
				{@const leftPct = ((l?.left ?? 0) * 100)}
				{@const widthPct = ((l?.width ?? 1) * 100)}
				<div
					class="event-block"
					class:compact
					style="top: {topPx(ev)}px; height: {h}px; left: {leftPct}%; width: {widthPct}%; background: {c.bg}; color: {c.fg};"
					on:click|stopPropagation={() => (popupEvent = ev)}
				>
					<div class="ev-title-row">
						<strong>{ev.summary}</strong>
						{#if h >= 20}
							<span class="ev-time">{formatTime(eventStart(ev))} – {formatTime(eventEnd(ev))}</span>
						{/if}
					</div>
					{#if !compact && h >= 64 && ev.location}
						<span class="ev-location">{ev.location}</span>
					{:else if !compact && h >= 72 && ev.description}
						<span class="ev-notes">{@html ev.description}</span>
					{/if}
				</div>
			{/each}
		</div>
	</div>
</div>

<EventPopup event={popupEvent} on:close={() => (popupEvent = null)} />

<style>
	.day-view {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
	}

	.day-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 1rem;
		flex-shrink: 0;
	}

	.day-header h2 {
		margin: 0;
		font-size: 1.2rem;
		flex: 1;
		text-align: center;
	}

	.nav-label {
		cursor: pointer;
		user-select: none;
	}

	.nav-btn {
		padding: 0.3rem 0.8rem;
		font-size: 1.2rem;
		flex-shrink: 0;
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		flex-shrink: 0;
	}

	.today-btn {
		padding: 0.2rem 0.6rem;
		font-size: 0.75rem;
	}

	.allday-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		padding: 0.3rem 1rem;
		flex-shrink: 0;
		border-bottom: 1px solid var(--pico-muted-border-color);
	}

	.chip {
		border-radius: 0.3rem;
		padding: 0.15rem 0.5rem;
		font-size: 0.8rem;
		cursor: pointer;
	}

	.scroll-area {
		flex: 1;
		overflow-y: auto;
		position: relative;
	}

	.time-grid {
		position: relative;
		margin-left: 5rem;
	}

	.hour-row {
		position: absolute;
		left: 0;
		right: 0;
		display: flex;
		align-items: flex-start;
	}

	.hour-label {
		position: absolute;
		left: -5rem;
		font-size: 0.7rem;
		color: var(--pico-muted-color);
		width: 4.8rem;
		text-align: right;
		padding-right: 0.4rem;
		line-height: 1;
	}

	.hour-weather {
		position: absolute;
		left: -5rem;
		top: 1rem;
		width: 4.8rem;
		display: flex;
		justify-content: flex-end;
		padding-right: 0.4rem;
	}

	.hour-line {
		flex: 1;
		border-top: 1px solid var(--pico-muted-border-color);
	}

	.event-block {
		position: absolute;
		box-sizing: border-box;
		border-radius: 0.4rem;
		padding: 0.15rem 0.5rem;
		overflow: hidden;
		font-size: 0.8rem;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		cursor: pointer;
		border-left: 3px solid rgba(0,0,0,0.15);
		/* small gutter between side-by-side columns */
		padding-left: calc(0.5rem + 2px);
		padding-right: calc(0.5rem + 2px);
	}

	/* Short events: vertically center the single title-row */
	.event-block.compact {
		justify-content: center;
		padding: 0 0.4rem;
	}

	.ev-title-row {
		display: flex;
		align-items: baseline;
		gap: 0.35rem;
		overflow: hidden;
		min-width: 0;
	}

	.event-block strong {
		font-size: 0.85rem;
		line-height: 1.2;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex: 1;
		min-width: 0;
	}

	.ev-time {
		font-size: 0.7rem;
		opacity: 0.8;
		flex-shrink: 0;
	}

	.ev-location {
		font-size: 0.7rem;
		opacity: 0.7;
		overflow: hidden;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
	}

	.ev-notes {
		font-size: 0.7rem;
		opacity: 0.7;
		overflow: hidden;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 3;
	}
</style>
