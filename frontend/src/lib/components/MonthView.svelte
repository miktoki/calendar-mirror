<script lang="ts">
	import type { CalendarEvent, WeatherRecord, TimeSeries } from '$lib/api';
	import { eventColor } from '$lib/api';
	import {
		eventsOnDay, startOfMonth, startOfWeek, addDays, addMonths,
		isSameDay, formatMonthYear, isAllDay,
		isoWeekNumber, localDateStr,

        time24h

	} from '$lib/dateUtils';
	import WeatherWidget from './WeatherWidget.svelte';
	import { currentView } from '$lib/stores';
	import { onMount, onDestroy } from 'svelte';
	import { createHorizontalSwipe, createPullToRefresh } from '$lib/calendarInteractions';

	export let events: CalendarEvent[];
	export let anchor: Date;
	export let weather: WeatherRecord | null = null;
	export let refresh: (() => Promise<void>) | undefined = undefined;
	export let lastFetchedAt: number = 0;

	const today = new Date();
	const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
	const CELL_HEADER_PX = 20;
	const CHIP_PX = 11;
	const SHOW_WEEK_TOUCH_DEBUG = true;
	const WEEK_TOUCH_TARGET_WIDTH_REM = 4;
	const WEEK_NUMBER_GUTTER_REM = 1.6;
	const FIRST_WEEKDAY_CONTENT_INSET_REM = WEEK_TOUCH_TARGET_WIDTH_REM - WEEK_NUMBER_GUTTER_REM;

	let gridEl: HTMLElement;
	let cellHeight = 80;
	let ro: ResizeObserver;
	const pullToRefresh = createPullToRefresh(() => refresh?.() ?? Promise.resolve());
	const swipe = createHorizontalSwipe(
		() => (anchor = addMonths(anchor, -1)),
		() => (anchor = addMonths(anchor, 1)),
	);

	// Max chips that visually fit in a cell (no overflow line reserved yet;
	// per-cell logic in template reserves 1 slot for "+N more" when needed).
	$: maxVisible = Math.max(1, Math.floor((cellHeight - CELL_HEADER_PX) / CHIP_PX));

	onMount(() => {
		ro = new ResizeObserver((entries) => {
			const h = entries[0]?.contentRect.height;
			if (h) cellHeight = h / 6;
		});
		ro.observe(gridEl);
	});

	onDestroy(() => ro?.disconnect());

	$: monthStart = startOfMonth(anchor);
	$: gridStart = startOfWeek(monthStart);
	$: cells = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
	$: currentMonth = anchor.getMonth();
	$: isCurrentMonth =
		anchor.getMonth() === today.getMonth() && anchor.getFullYear() === today.getFullYear();

	$: timeseries = weather?.forecast?.properties?.timeseries ?? [];

	function buildCells(cells: Date[], timeseries: TimeSeries[]): { day: Date; series: TimeSeries[] }[] {
		return cells.map((day) => {
			const key = localDateStr(day);
			return { day, series: timeseries.filter((ts) => localDateStr(new Date(ts.time)) === key) };
		});
	}

	$: cellsWithWeather = buildCells(cells, timeseries);

	function shouldHandleCalendarKeys(event: KeyboardEvent): boolean {
		if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return false;
		const target = event.target;
		if (!(target instanceof HTMLElement)) return true;
		return !target.closest('input, textarea, select, [contenteditable="true"]');
	}

	function onWindowKeydown(event: KeyboardEvent) {
		if (!shouldHandleCalendarKeys(event)) return;
		if (event.key === 'ArrowLeft') {
			event.preventDefault();
			anchor = addMonths(anchor, -1);
			return;
		}
		if (event.key === 'ArrowRight') {
			event.preventDefault();
			anchor = addMonths(anchor, 1);
			return;
		}
	}
</script>

<svelte:window on:keydown={onWindowKeydown} />

<div
	class="month-view"
	role="presentation"
	on:touchstart={(event) => {
		pullToRefresh.onTouchStart(event, 0);
		swipe.onTouchStart(event);
	}}
	on:touchmove={(event) => {
		pullToRefresh.onTouchMove(event, 0);
		swipe.onTouchMove(event);
	}}
	on:touchend={() => {
		pullToRefresh.onTouchEnd();
		swipe.onTouchEnd();
	}}
>
	<header class="month-header">
		<div class="header-left">
			<button class="outline nav-btn" on:click={() => (anchor = addMonths(anchor, -1))}>‹</button>
		</div>
		<h2 class="period">{formatMonthYear(anchor)}</h2>
		<div class="header-right">
			{#if lastFetchedAt}
				<span class="updated">Updated {time24h(lastFetchedAt)}</span>
			{/if}
			{#if !isCurrentMonth}
				<button class="outline today-btn" on:click={() => (anchor = new Date())}>Today</button>
			{/if}
			<button class="outline nav-btn" on:click={() => (anchor = addMonths(anchor, 1))}>›</button>
		</div>
	</header>

	<div class="dow-row">
		<div class="wnum-header"></div>
		{#each DOW as d}<div class="dow">{d}</div>{/each}
	</div>

	<div class="cal-grid" bind:this={gridEl}>
		{#each { length: 6 } as _, rowIdx}
			{@const rowStart = cellsWithWeather[rowIdx * 7].day}
			<div class="week-num">
				<button
					type="button"
					class="week-touch-target"
					class:debug-touch={SHOW_WEEK_TOUCH_DEBUG}
					on:click={() => { anchor = rowStart; currentView.set('week'); }}
					aria-label={`Open week ${isoWeekNumber(rowStart)}`}
				>
					<span class="week-num-label">{isoWeekNumber(rowStart)}</span>
				</button>
			</div>
			{#each cellsWithWeather.slice(rowIdx * 7, rowIdx * 7 + 7) as { day, series }, colIdx}
				{@const dayEvents = eventsOnDay(events, day)}
				{@const visible = dayEvents.length > maxVisible ? dayEvents.slice(0, maxVisible - 1) : dayEvents}
				{@const overflow = dayEvents.length - visible.length}
				<button
					type="button"
					class="cal-cell"
					class:first-weekday={colIdx === 0}
					class:other-month={day.getMonth() !== currentMonth}
					class:today={isSameDay(day, today)}
					style:--first-weekday-content-inset={colIdx === 0 ? `${FIRST_WEEKDAY_CONTENT_INSET_REM}rem` : '0rem'}
					on:click={() => { anchor = day; currentView.set('day'); }}
				>
					<div class="cell-header">
						<span class="day-num">{day.getDate()}</span>
						<WeatherWidget {series} hour={12} mode="day" />
					</div>
					<div class="event-list">
						{#each visible as ev}
							{@const c = eventColor(ev)}
							<div class="ev-chip" style="background: {c.bg}; color: {c.fg};">
								<span class="ev-title">{ev.summary}</span>
							</div>
						{/each}
						{#if overflow > 0}
							<div class="overflow">+{overflow} more</div>
						{/if}
					</div>
				</button>
			{/each}
		{/each}
	</div>
</div>
<style>
	.month-view {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
	}

	.month-header {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		padding: 0.5rem 1rem;
		flex-shrink: 0;
		gap: 0.5rem;
	}

	.header-left {
		display: flex;
		justify-content: flex-start;
	}

	.period {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 600;
		text-align: center;
		line-height: 1.2;
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

	.dow-row {
		display: grid;
		grid-template-columns: 1.6rem repeat(7, 1fr);
		flex-shrink: 0;
		border-bottom: 1px solid var(--pico-muted-border-color);
	}

	.wnum-header {
		border-right: 1px solid var(--pico-muted-border-color);
	}

	.dow {
		text-align: center;
		font-size: 0.75rem;
		font-weight: 600;
		padding: 0.2rem 0;
		color: var(--pico-muted-color);
	}

	.cal-grid {
		flex: 1;
		display: grid;
		grid-template-columns: 1.6rem repeat(7, 1fr);
		grid-template-rows: repeat(6, 1fr);
		overflow: hidden;
	}

	.week-num {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.6rem;
		color: var(--pico-muted-color);
		border-right: 1px solid var(--pico-muted-border-color);
		border-bottom: 1px solid var(--pico-muted-border-color);
		user-select: none;
		overflow: visible;
		z-index: 1;
	}

	.week-touch-target {
		all: unset;
		position: absolute;
		left: 0;
		top: 0;
		height: 100%;
		width: max(100%, 4rem);
		display: flex;
		align-items: center;
		justify-content: flex-start;
		cursor: pointer;
		border-radius: 0.25rem;
	}

	/* .week-touch-target.debug-touch {
		outline: 1px dashed rgba(255, 92, 92, 0.8);
		outline-offset: -1px;
		background: color-mix(in srgb, rgba(255, 92, 92, 0.14) 100%, transparent);
	} */

	.week-num-label {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.6rem;
		height: 100%;
		pointer-events: none;
	}

	.cal-cell {
		border-right: 1px solid var(--pico-muted-border-color);
		border-bottom: 1px solid var(--pico-muted-border-color);
		padding: 0.2rem 0.3rem;
		width: 100%;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		border-top: 0;
		border-left: 0;
		cursor: pointer;
		user-select: none;
	}

	.cal-cell.first-weekday .event-list {
		padding-left: calc(var(--first-weekday-content-inset) - 0.3rem);
	}

	.cell-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		min-height: 1.15rem;
		flex-shrink: 0;
	}

	.cal-cell.other-month {
		opacity: 0.35;
	}

	.day-num {
		font-size: 0.8rem;
		font-weight: 600;
		line-height: 1.15;
		flex-shrink: 0;
	}

	.cal-cell.today .day-num {
		background: var(--pico-primary);
		color: var(--pico-primary-inverse);
		border-radius: 50%;
		width: 1.5rem;
		height: 1.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.event-list {
		display: flex;
		flex-direction: column;
		gap: 0;
		overflow: hidden;
	}

	.ev-chip {
		display: flex;
		gap: 0;
		align-items: baseline;
		background-image: none;
		border-left: 2px solid rgba(0, 0, 0, 0.15);
		border-radius: 0.2rem;
		padding: 0 0.24rem;
		font-size: 0.68rem;
		font-weight: 500;
		line-height: 1.16;
		overflow: hidden;
		white-space: nowrap;
	}

	.ev-title {
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.overflow {
		font-size: 0.62rem;
		line-height: 1.1;
		color: var(--pico-muted-color);
		padding-left: 0.15rem;
	}
</style>
