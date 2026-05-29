<script lang="ts">
	import type { CalendarEvent, CalendarMeta, WeatherRecord, TimeSeries } from '$lib/api';
	import type { TimedSegment, TimedEventChipContent } from '$lib/dateUtils';
	import {
		isAllDay, formatTime, isSameDay,
		eventsOnDay, startOfWeek, addDays, formatMonthYear, localDateStr,
		isoWeekNumber, timedSegmentsForDay, layoutOverlappingSegments, timedEventChipContent, plainTextFromHtml,

        time24h

	} from '$lib/dateUtils';
	import WeatherWidget from './WeatherWidget.svelte';
	import { currentView } from '$lib/stores';
	import EventPopup from './EventPopup.svelte';
	import AllDayEventChip from './AllDayEventChip.svelte';
	import TimedEventChip from './TimedEventChip.svelte';
	import { createHorizontalSwipe, createPullToRefresh, defaultHourScrollTop, scrollHoursBy } from '$lib/calendarInteractions';
	import { onMount } from 'svelte';

	export let events: CalendarEvent[];
	export let calendars: CalendarMeta[] = [];
	export let anchor: Date;
	export let weather: WeatherRecord | null = null;
	export let refresh: (() => Promise<void>) | undefined = undefined;
	export let lastFetchedAt: number = 0;

	let popupEvent: CalendarEvent | null = null;
	let scrollRow: HTMLDivElement;

	$: weekStart = startOfWeek(anchor);
	$: weekNumber = isoWeekNumber(weekStart);
	$: days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
	$: calendarBadges = calendars
		.filter((calendar) => calendar.summary)
		.map((calendar) => ({
			label: calendar.summary.slice(0, 6),
			bg: calendar.background_color,
			fg: calendar.foreground_color,
		}));

	$: timeseries = weather?.forecast?.properties?.timeseries ?? [];
	let daysWithWeather: { day: Date; series: TimeSeries[] }[];
	$: daysWithWeather = days.map((day) => {
		const key = localDateStr(day);
		return { day, series: timeseries.filter((ts) => localDateStr(new Date(ts.time)) === key) };
	});

	const HOUR_HEIGHT = 56;
	const START_HOUR = 6;
	const END_HOUR = 23;
	const DEFAULT_VISIBLE_START_HOUR = 8;
	const DEFAULT_VISIBLE_END_HOUR = 20;
	const hours = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, i) => START_HOUR + i);
	const today = new Date();
	const pullToRefresh = createPullToRefresh(() => refresh?.() ?? Promise.resolve());
	const swipe = createHorizontalSwipe(
		() => (anchor = addDays(anchor, -7)),
		() => (anchor = addDays(anchor, 7)),
	);

	onMount(() => {
		if (scrollRow) {
			scrollRow.scrollTop = defaultHourScrollTop(
				START_HOUR,
				DEFAULT_VISIBLE_START_HOUR,
				DEFAULT_VISIBLE_END_HOUR,
				END_HOUR,
				HOUR_HEIGHT,
				scrollRow.clientHeight,
			);
		}
	});

	$: isCurrentWeek = days.some((d) => d.toDateString() === today.toDateString());

	$: daysData = days.map((day) => {
		const dayEvs = eventsOnDay(events, day);
		const segments = timedSegmentsForDay(dayEvs, day, START_HOUR);
		const timedSegs = segments.filter((s) => !s.isFullDay);
		const layout = layoutOverlappingSegments(timedSegs);
		const timedRender = timedSegs.map((seg) => {
			const h = segHeightPx(seg.displayStart, seg.displayEnd);
			const evLayout = layout.get(seg.id);
			const chip = timedEventChipContent(h, evLayout?.width ?? 1, Boolean(seg.ev.description), 'week');
			const description = plainTextFromHtml(seg.ev.description);
			const leftPct = (evLayout?.left ?? 0) * 100;
			const widthPct = (evLayout?.width ?? 1) * 100;
			const style = `top: ${segTopPx(seg.displayStart)}px; height: ${h}px; left: calc(1px + ${leftPct}%); width: calc(${widthPct}% - 2px);`;
			return { seg, config: weekChipConfig(seg, chip, description, style) };
		});
		return {
			day,
			allDayEvs: dayEvs.filter(isAllDay),
			fullDaySegs: segments.filter((s) => s.isFullDay),
			timedRender,
		};
	});

	function segTopPx(displayStart: Date): number {
		const minutes = displayStart.getHours() * 60 + displayStart.getMinutes() - START_HOUR * 60;
		return Math.max(0, (minutes / 60) * HOUR_HEIGHT);
	}

	function segHeightPx(displayStart: Date, displayEnd: Date): number {
		const dur = (displayEnd.getTime() - displayStart.getTime()) / 60000;
		return Math.max(20, (dur / 60) * HOUR_HEIGHT);
	}

	function weekChipConfig(
		segment: TimedSegment,
		chip: TimedEventChipContent,
		description: string,
		style: string,
	) {
		let startText: string;
		let endText: string | null;
		if (segment.isContinuation) {
			startText = '';
			endText = formatTime(segment.end);
		} else if (segment.endsAtMidnight) {
			startText = formatTime(segment.start);
			endText = '';
		} else {
			startText = formatTime(segment.start);
			endText = chip.showEndTime ? formatTime(segment.end) : null;
		}
		return {
			startText,
			endText,
			description,
			compact: chip.compact,
			narrow: chip.narrow,
			titleLines: chip.titleLines,
			descriptionLines: chip.descriptionLines,
			density: 'week' as const,
			separatorColor: 'rgba(255, 255, 255, 0.35)',
			style,
		};
	}

	function shouldHandleCalendarKeys(event: KeyboardEvent): boolean {
		if (popupEvent || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return false;
		const target = event.target;
		if (!(target instanceof HTMLElement)) return true;
		return !target.closest('input, textarea, select, [contenteditable="true"]');
	}

	function onWindowKeydown(event: KeyboardEvent) {
		if (!shouldHandleCalendarKeys(event)) return;
		if (scrollRow && event.key === 'PageDown') {
			event.preventDefault();
			scrollHoursBy(scrollRow, 3, HOUR_HEIGHT);
			return;
		}
		if (scrollRow && event.key === 'PageUp') {
			event.preventDefault();
			scrollHoursBy(scrollRow, -3, HOUR_HEIGHT);
			return;
		}
		if (scrollRow && event.key === 'Home') {
			event.preventDefault();
			scrollRow.scrollTo({ top: 0, behavior: 'smooth' });
			return;
		}
		if (scrollRow && event.key === 'End') {
			event.preventDefault();
			scrollRow.scrollTo({ top: scrollRow.scrollHeight, behavior: 'smooth' });
			return;
		}
		if (event.key === 'ArrowLeft') {
			event.preventDefault();
			anchor = addDays(anchor, -7);
			return;
		}
		if (event.key === 'ArrowRight') {
			event.preventDefault();
			anchor = addDays(anchor, 7);
			return;
		}
		if (event.key === 'ArrowUp') {
			event.preventDefault();
			currentView.set('month');
			return;
		}
	}
</script>

<svelte:window on:keydown={onWindowKeydown} />

<div class="week-view">
	<header class="week-header">
		<div class="header-left">
			<button class="outline nav-btn" on:click={() => (anchor = addDays(anchor, -7))}>‹</button>
			{#if calendarBadges.length}
				<div class="calendar-badges">
					{#each calendarBadges as badge}
						<span class="calendar-badge" style="background: {badge.bg}; color: {badge.fg};">{badge.label}</span>
					{/each}
				</div>
			{/if}
		</div>
		<button type="button" class="period nav-label" on:click={() => currentView.set('month')}>
			<span class="period-title">{formatMonthYear(weekStart)}</span>
			<span class="period-week-number" aria-hidden="true">W{weekNumber}</span>
		</button>
		<div class="header-right">
			{#if lastFetchedAt}
				<span class="updated">Updated {time24h(lastFetchedAt)}</span>
			{/if}
			{#if !isCurrentWeek}
				<button class="outline today-btn" on:click={() => (anchor = new Date())}>Today</button>
			{/if}
			<button class="outline nav-btn" on:click={() => (anchor = addDays(anchor, 7))}>›</button>
		</div>
	</header>

	<div class="grid-wrapper">
		<div class="time-col-header"></div>
		{#each daysWithWeather as { day, series }}
			<button
				type="button"
				class="day-col-header"
				class:today={isSameDay(day, today)}
				on:click={() => { anchor = day; currentView.set('day'); }}
			>
				<div class="day-label-row">
					<span class="dow">{day.toLocaleDateString([], { weekday: 'short' })}</span>
					<span class="dom" class:today={isSameDay(day, today)}>{day.getDate()}</span>
				</div>
				<WeatherWidget {series} hour={12} mode="day" />
			</button>
		{/each}

		<div class="allday-gutter"></div>
		{#each daysData as { allDayEvs, fullDaySegs }}
			<div class="allday-cell">
				{#each allDayEvs as ev}
					<AllDayEventChip event={ev} density="week" onOpen={(e) => (popupEvent = e)} />
				{/each}
				{#each fullDaySegs as seg}
					<AllDayEventChip event={seg.ev} density="week" onOpen={(e) => (popupEvent = e)} />
				{/each}
			</div>
		{/each}

		<div
			class="scroll-row"
			role="presentation"
			bind:this={scrollRow}
			on:touchstart={(event) => {
				pullToRefresh.onTouchStart(event, scrollRow?.scrollTop ?? 0);
				swipe.onTouchStart(event);
			}}
			on:touchmove={(event) => {
				pullToRefresh.onTouchMove(event, scrollRow?.scrollTop ?? 0);
				swipe.onTouchMove(event);
			}}
			on:touchend={() => {
				pullToRefresh.onTouchEnd();
				swipe.onTouchEnd();
			}}
		>
			<div class="time-col">
				{#each hours as h}
					<div class="hour-label" style="height: {HOUR_HEIGHT}px">
						{String(h).padStart(2, '0')}:00
					</div>
				{/each}
			</div>

			{#each daysData as { timedRender }}
				<div class="day-col" style="height: {(END_HOUR - START_HOUR + 1) * HOUR_HEIGHT}px">
					{#each hours as h}
						<div class="hour-line" style="top: {(h - START_HOUR) * HOUR_HEIGHT}px"></div>
					{/each}

					{#each timedRender as { seg, config }}
						<TimedEventChip
							event={seg.ev}
							{config}
							onOpen={(e) => (popupEvent = e)}
						/>
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
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		padding: 0.5rem 1rem;
		flex-shrink: 0;
		column-gap: 0.5rem;
	}

	.header-left {
		display: flex;
		justify-content: flex-start;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
	}

	.period {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		margin: 0;
		min-height: 1.45rem;
		font-size: 1.2rem;
		font-weight: 600;
		position: relative;
		line-height: 1.2;
	}

	.period-title {
		display: inline-block;
		line-height: 1.2;
	}

	.period-week-number {
		position: absolute;
		right: -2.6rem;
		top: 0.2rem;
		font-size: 0.82rem;
		font-weight: 500;
		opacity: 0.45;
		letter-spacing: 0.02em;
	}

	.calendar-badges {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-start;
		gap: 0.3rem;
		max-width: min(20rem, 40vw);
		overflow: hidden;
	}

	.calendar-badge {
		border-radius: 999px;
		font-size: 0.68rem;
		font-weight: 600;
		line-height: 1;
		padding: 0.18rem 0.45rem;
		white-space: nowrap;
	}

	.nav-btn {
		padding: 0.3rem 0.8rem;
		font-size: 1.2rem;
		flex-shrink: 0;
	}

	.header-right {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 0.3rem;
		flex-shrink: 0;
	}

	.updated {
		font-size: 0.75rem;
		color: var(--pico-muted-color);
	}

	.today-btn {
		padding: 0.2rem 0.6rem;
		font-size: 0.75rem;
	}

	.grid-wrapper {
		flex: 1;
		overflow: hidden;
		display: grid;
		grid-template-columns: 3rem repeat(7, minmax(0, 1fr));
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
		min-width: 0;
		padding: 0.2rem 0;
		border-bottom: 1px solid var(--pico-muted-border-color);
		font-size: 0.75rem;
		cursor: pointer;
		user-select: none;
		gap: 0.1rem;
		width: 100%;
		border: 0;
		background: transparent;
		text-align: center;
		gap: 0.1rem;
	}

	.day-label-row {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.3rem;
		line-height: 1;
	}

	.nav-label {
		padding: 0;
		border: 0;
		background: transparent;
		color: inherit;
		cursor: pointer;
		user-select: none;
	}

	.day-col-header.today {
		color: var(--pico-primary);
	}

	.dom {
		font-size: 0.92rem;
		font-weight: 600;
		line-height: 1;
	}

	.dom.today {
		background: var(--pico-primary);
		color: var(--pico-primary-inverse);
		border-radius: 50%;
		width: 1.35rem;
		height: 1.35rem;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.allday-cell {
		min-height: 1.6rem;
		min-width: 0;
		padding: 0.1rem 0.2rem;
		border-bottom: 1px solid var(--pico-muted-border-color);
		display: flex;
		align-items: flex-start;
		align-content: flex-start;
		flex-wrap: wrap;
		column-gap: 0.15rem;
		row-gap: 1px;
	}

	.scroll-row {
		grid-column: 1 / -1;
		display: grid;
		grid-template-columns: 3rem repeat(7, minmax(0, 1fr));
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
		min-width: 0;
		border-right: 1px solid var(--pico-muted-border-color);
	}

	.hour-line {
		position: absolute;
		left: 0;
		right: 0;
		border-top: 1px solid var(--pico-muted-border-color);
	}
</style>
