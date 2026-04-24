<script lang="ts">
	import type { CalendarEvent, WeatherRecord, TimeSeries } from '$lib/api';
	import { eventColor } from '$lib/api';
	import {
		type TimedSegment,
		eventStart, eventEnd, isAllDay, formatTime, isSameDay,
		eventsOnDay, startOfWeek, addDays, formatDate, formatMonthYear, localDateStr, layoutOverlappingTimedEvents,
		timedSegmentsForDay, layoutOverlappingSegments, splitEventIntoDaySegments,
		timedEventChipContent, plainTextFromHtml
	} from '$lib/dateUtils';
	import { weatherDayKeyForLocalDay } from '$lib/dateUtils';
	import WeatherWidget from './WeatherWidget.svelte';
	import { currentView } from '$lib/stores';
	import EventPopup from './EventPopup.svelte';
	import { onMount } from 'svelte';
	import AllDayEventChip from './AllDayEventChip.svelte';
	import TimedEventChip from './TimedEventChip.svelte';

	export let events: CalendarEvent[];
	export let anchor: Date;
	export let weather: WeatherRecord | null = null;
	export let weatherByDay: Record<string, TimeSeries[]> = {};

	let popupEvent: CalendarEvent | null = null;

	$: weekStart = startOfWeek(anchor);
	$: days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

	const HOUR_HEIGHT = 56;
	const START_HOUR = 6;
	const END_HOUR = 23;
	const hours = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, i) => START_HOUR + i);
	const today = new Date();

	$: isCurrentWeek = days.some((d) => d.toDateString() === today.toDateString());

	// Precompute segments and layouts per day for use in the template
	$: segmentsByDay = new Map(days.map((d) => [localDateStr(d), timedSegmentsForDay(events, d, START_HOUR)]));
	$: layoutByDay = new Map(Array.from(segmentsByDay.entries()).map(([k, segs]) => [k, layoutOverlappingSegments(segs.filter(s => !s.isFullDay))]));

	// Full-day events derived from timed multi-day events (segments that cover the whole day)
	$: allDayFromTimedByDay = new Map(days.map((d) => [localDateStr(d), (segmentsByDay.get(localDateStr(d)) ?? []).filter((s) => s.isFullDay).map((s) => s.ev)]));

	$: console.debug && console.debug('segmentsByDay updated', Array.from(segmentsByDay.entries()).map(([k, v]) => [k, v.map(s => ({ id: s.id, isFullDay: s.isFullDay }))]));
	$: console.debug && console.debug('allDayFromTimedByDay updated', Array.from(allDayFromTimedByDay.entries()));

	function allDayEventsForDay(day: Date) {
		const base = eventsOnDay(events, day).filter(isAllDay);
		const extra = allDayFromTimedByDay.get(localDateStr(day)) ?? [];
		const byId = new Map();
		for (const e of base) byId.set(e.id, e);
		for (const e of extra) byId.set(e.id, e);
		return Array.from(byId.values());
	}

	// Compute all-day events for each visible day by scanning events directly.
	$: allDayEventsByDay = (() => {
		const map = new Map<string, CalendarEvent[]>();
		for (const d of days) map.set(localDateStr(d), []);

		// Add explicit all-day events
		for (const d of days) {
			const list = eventsOnDay(events, d).filter(isAllDay);
			map.set(localDateStr(d), [...(map.get(localDateStr(d)) ?? []), ...list]);
		}

		// For timed events, if they fully cover a calendar day (start < dayStart && end > dayEnd), mark as all-day
		for (const ev of events) {
			if (isAllDay(ev)) continue;
			const s = eventStart(ev);
			const e = eventEnd(ev);
			for (const d of days) {
				const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate());
				const dayEnd = new Date(dayStart.getFullYear(), dayStart.getMonth(), dayStart.getDate() + 1);
				if (s.getTime() <= dayStart.getTime() && e.getTime() >= dayEnd.getTime()) {
					map.get(localDateStr(d))!.push(ev);
				}
			}
		}

		// Deduplicate per-day
		return new Map(Array.from(map.entries()).map(([k, arr]) => [k, Array.from(new Map(arr.map(a => [a.id, a])).values())]));
	})();

	$: console.debug && console.debug('allDayEventsByDay', Array.from(allDayEventsByDay.entries()).map(([k, v]) => [k, v.map(e => e.id)]));

	$: daysWithWeather = days.map((day) => ({
		day,
		series: weatherByDay[weatherDayKeyForLocalDay(day)] ?? []
	}));

	onMount(() => {
		// Debug: log segments/all-day maps to help diagnose disappearing chips
		console.debug('WeekView mounted, events:', events?.length);
		console.debug('segmentsByDay:', Array.from(segmentsByDay.entries()).map(([k, v]) => [k, v.map(s => ({id: s.id, isFullDay: s.isFullDay}))]));
		console.debug('allDayFromTimedByDay:', Array.from(allDayFromTimedByDay.entries()));
	});


	function topPxFromDate(s: Date): number {
		const minutes = s.getHours() * 60 + s.getMinutes() - START_HOUR * 60;
		return Math.max(0, (minutes / 60) * HOUR_HEIGHT);
	}

	function heightPxFromDates(s: Date, e: Date): number {
		const dur = (e.getTime() - s.getTime()) / 60000;
		return Math.max(20, (dur / 60) * HOUR_HEIGHT);
	}

	function segmentStartText(seg: TimedSegment): string {
		return formatTime(eventStart(seg.ev));
	}

	function segmentEndText(seg: TimedSegment): string | null {
		const end = eventEnd(seg.ev);
		return isSameDay(end, seg.displayStart) ? formatTime(end) : null;
	}

	function openPopup(ev: CalendarEvent) {
		popupEvent = ev;
	}

	function timedStyle(top: number, height: number, leftPct: number, widthPct: number): string {
		return `top: ${top}px; height: ${height}px; left: ${leftPct}%; width: ${widthPct}%;`;
	}

	// removed unused layoutForDay per request

// Choose a separator color that contrasts with the event background.
function pickSeparatorColor(bg: string): string {
	// handle hex like #rrggbb
	const hex = bg.trim();
	let r=0,g=0,b=0;
	const m = /^#([0-9a-fA-F]{6})$/.exec(hex);
	if (m) {
		r = parseInt(m[1].slice(0,2), 16);
		g = parseInt(m[1].slice(2,4), 16);
		b = parseInt(m[1].slice(4,6), 16);
	} else {
		// fallback: try rgb(...) or default to dark separator
		const mm = /rgb\s*\(\s*(\d+),\s*(\d+),\s*(\d+)\s*\)/.exec(hex);
		if (mm) {
			r = Number(mm[1]); g = Number(mm[2]); b = Number(mm[3]);
		} else {
			return 'rgba(0,0,0,0.18)';
		}
	}
	// relative luminance
	const srgb = [r,g,b].map((v) => v/255).map((c) => c <= 0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4));
	const lum = 0.2126*srgb[0] + 0.7152*srgb[1] + 0.0722*srgb[2];
	// if background is light, use dark separator; else use light separator
	return lum > 0.6 ? 'rgba(0,0,0,0.22)' : 'rgba(255,255,255,0.22)';
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


		<div class="scroll-row">
			<div class="time-col">
				{#each hours as h}
					<div class="hour-label" style="height: {HOUR_HEIGHT}px">
						{String(h).padStart(2, '0')}:00
					</div>
				{/each}
			</div>

			{#each days as day}
				<div class="day-col" style="height: {(END_HOUR - START_HOUR + 1) * HOUR_HEIGHT}px">
					{#each hours as h}
						<div class="hour-line" style="top: {(h - START_HOUR) * HOUR_HEIGHT}px"></div>
					{/each}

						{#each (segmentsByDay.get(localDateStr(day)) ?? []).filter(s => !s.isFullDay) as seg}
							{@const dayLayout = layoutByDay.get(localDateStr(day))}
							{@const evStart = eventStart(seg.ev)}
							{@const c = eventColor(seg.ev)}
							{@const hpx = heightPxFromDates(seg.displayStart, seg.displayEnd)}
							{@const l = dayLayout ? dayLayout.get(seg.id) : undefined}
							{@const leftPct = ((l?.left ?? 0) * 100)}
							{@const widthPct = ((l?.width ?? 1) * 100)}
							{@const chip = timedEventChipContent(hpx, l?.width ?? 1, Boolean(seg.ev.description))}
							{@const description = plainTextFromHtml(seg.ev.description)}
							{@const endText = chip.showEndTime ? segmentEndText(seg) : null}
							{@const sep = pickSeparatorColor(c.bg)}
							{@const top = topPxFromDate(seg.displayStart)}
							{@const blockStyle = timedStyle(top, hpx, leftPct, widthPct)}
							<TimedEventChip
								event={seg.ev}
								startText={segmentStartText(seg)}
								endText={endText}
								description={description}
								compact={chip.compact}
								narrow={chip.narrow}
								titleLines={chip.titleLines}
								descriptionLines={chip.descriptionLines}
								density="week"
								separatorColor={sep}
								style={blockStyle}
								onOpen={openPopup}
							></TimedEventChip>
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
		gap: 8px;
		justify-content: space-between;
	}

.event-block {
	position: relative;
	/* flat appearance, separator uses per-event variable for contrast */
	border-bottom: 2px solid var(--event-sep, rgba(0,0,0,0.18));
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
		min-height: 1.3rem;
		padding: 0.08rem 0.14rem;
		border-bottom: 1px solid var(--pico-muted-border-color);
		display: flex;
		flex-direction: column;
		align-items: stretch;
		justify-content: flex-start;
		gap: 0.07rem;
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

</style>
