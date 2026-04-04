<script lang="ts">
	import type { CalendarEvent, WeatherRecord, TimeSeries } from '$lib/api';
	import { eventColor } from '$lib/api';
	import {
		eventStart, eventEnd, isAllDay, formatTime, isSameDay,
		eventsOnDay, startOfWeek, addDays, formatDate, formatMonthYear, localDateStr, layoutOverlappingTimedEvents
	} from '$lib/dateUtils';
	import { weatherDayKeyForLocalDay } from '$lib/dateUtils';
	import WeatherWidget from './WeatherWidget.svelte';
	import { currentView } from '$lib/stores';
	import EventPopup from './EventPopup.svelte';

	export let events: CalendarEvent[];
	export let anchor: Date;
	export let weather: WeatherRecord | null = null;
	export let weatherByDay: Record<string, TimeSeries[]> = {};

	let popupEvent: CalendarEvent | null = null;

	$: weekStart = startOfWeek(anchor);
	$: days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

	$: daysWithWeather = days.map((day) => ({
		day,
		series: weatherByDay[weatherDayKeyForLocalDay(day)] ?? []
	}));

	const HOUR_HEIGHT = 56;
	const START_HOUR = 6;
	const END_HOUR = 23;
	const hours = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, i) => START_HOUR + i);
	const today = new Date();

	$: isCurrentWeek = days.some((d) => d.toDateString() === today.toDateString());

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

	function layoutForDay(day: Date) {
		return layoutOverlappingTimedEvents(eventsOnDay(events, day).filter((e) => !isAllDay(e)));
	}
</script>

<div class="week-view">
	<header class="week-header">
		<button class="outline nav-btn" on:click={() => (anchor = addDays(anchor, -7))}>‹</button>
		<span class="period nav-label" on:click={() => currentView.set('month')}>{formatMonthYear(weekStart)}</span>
		<div class="header-right">
			{#if !isCurrentWeek}
				<button class="outline today-btn" on:click={() => (anchor = new Date())}>Today</button>
			{/if}
			<button class="outline nav-btn" on:click={() => (anchor = addDays(anchor, 7))}>›</button>
		</div>
	</header>

	<div class="grid-wrapper">
		<div class="time-col-header"></div>
		{#each daysWithWeather as { day, series }}
			<div
				class="day-col-header"
				class:today={isSameDay(day, today)}
				on:click={() => { anchor = day; currentView.set('day'); }}
			>
				<span class="dow">{day.toLocaleDateString([], { weekday: 'short' })}</span>
				<span class="dom" class:today={isSameDay(day, today)}>{day.getDate()}</span>
				<WeatherWidget {series} hour={12} mode="day" />
			</div>
		{/each}

		<div class="allday-gutter"></div>
		{#each days as day}
			<div class="allday-cell">
				{#each eventsOnDay(events, day).filter(isAllDay) as ev}
					{@const c = eventColor(ev)}
					<span class="chip" style="background: {c.bg}; color: {c.fg};" on:click|stopPropagation={() => (popupEvent = ev)}>{ev.summary}</span>
				{/each}
			</div>
		{/each}

		<div class="scroll-row">
			<div class="time-col">
				{#each hours as h}
					<div class="hour-label" style="height: {HOUR_HEIGHT}px">
						{String(h).padStart(2, '0')}:00
					</div>
				{/each}
			</div>

			{#each days as day}
				{@const dayLayout = layoutForDay(day)}
				<div class="day-col" style="height: {(END_HOUR - START_HOUR + 1) * HOUR_HEIGHT}px">
					{#each hours as h}
						<div class="hour-line" style="top: {(h - START_HOUR) * HOUR_HEIGHT}px"></div>
					{/each}

					{#each eventsOnDay(events, day).filter((e) => !isAllDay(e)) as ev}
						{@const c = eventColor(ev)}
						{@const h = heightPx(ev)}
						{@const compact = h < 32}
						{@const l = dayLayout.get(ev.id)}
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
									<span class="ev-time">{formatTime(eventStart(ev))}</span>
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
			{/each}
		</div>
	</div>
</div>

<EventPopup event={popupEvent} on:close={() => (popupEvent = null)} />

<style>
	.week-view {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
	}

	.week-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.4rem 1rem;
		flex-shrink: 0;
	}

	.period {
		font-size: 1rem;
		font-weight: 600;
		flex: 1;
		text-align: center;
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

	.grid-wrapper {
		flex: 1;
		overflow: hidden;
		display: grid;
		grid-template-columns: 3rem repeat(7, 1fr);
		grid-template-rows: auto auto 1fr;
	}

	.time-col-header,
	.allday-gutter {
		border-right: 1px solid var(--pico-muted-border-color);
	}

	.day-col-header {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 0.25rem 0;
		border-bottom: 1px solid var(--pico-muted-border-color);
		font-size: 0.75rem;
		cursor: pointer;
		user-select: none;
	}


	.nav-label {
		cursor: pointer;
		user-select: none;
	}

	.day-col-header.today {
		color: var(--pico-primary);
	}

	.dom {
		font-size: 1.1rem;
		font-weight: 600;
		line-height: 1.4;
	}

	.dom.today {
		background: var(--pico-primary);
		color: var(--pico-primary-inverse);
		border-radius: 50%;
		width: 1.8rem;
		height: 1.8rem;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.allday-cell {
		min-height: 1.6rem;
		padding: 0.1rem 0.2rem;
		border-bottom: 1px solid var(--pico-muted-border-color);
		display: flex;
		flex-wrap: wrap;
		gap: 0.15rem;
	}

	.chip {
		border-radius: 0.25rem;
		padding: 0.1rem 0.35rem;
		font-size: 0.7rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 100%;
		cursor: pointer;
	}

	.scroll-row {
		grid-column: 1 / -1;
		display: grid;
		grid-template-columns: 3rem repeat(7, 1fr);
		overflow-y: auto;
	}

	.time-col {
		border-right: 1px solid var(--pico-muted-border-color);
	}

	.hour-label {
		display: flex;
		align-items: flex-start;
		justify-content: flex-end;
		padding-right: 0.4rem;
		padding-top: 0.1rem;
		font-size: 0.65rem;
		color: var(--pico-muted-color);
	}

	.day-col {
		position: relative;
		border-right: 1px solid var(--pico-muted-border-color);
	}

	.hour-line {
		position: absolute;
		left: 0;
		right: 0;
		border-top: 1px solid var(--pico-muted-border-color);
	}

	.event-block {
		position: absolute;
		box-sizing: border-box;
		border-left: 3px solid rgba(0, 0, 0, 0.15);
		border-radius: 0.3rem;
		padding: 0.2rem 0.3rem;
		overflow: hidden;
		font-size: 0.72rem;
		display: flex;
		flex-direction: column;
		gap: 0.05rem;
		cursor: pointer;
		margin-left: 1px;
		margin-right: 1px;
	}

	/* Short events: collapse to a single line */
	.event-block.compact {
		padding: 0 0.3rem;
		justify-content: center;
	}

	.ev-title-row {
		display: flex;
		align-items: baseline;
		gap: 0.3rem;
		overflow: hidden;
		min-width: 0;
	}

	.event-block strong {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		font-size: 0.75rem;
		flex: 1;
		min-width: 0;
	}

	.ev-time {
		opacity: 0.85;
		font-size: 0.65rem;
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
