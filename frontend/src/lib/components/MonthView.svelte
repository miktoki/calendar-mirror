<script lang="ts">
	import type { CalendarEvent, WeatherRecord, TimeSeries } from '$lib/api';
	import { eventColor } from '$lib/api';
	import {
		eventsOnDay, startOfMonth, startOfWeek, addDays, addMonths,
		isSameDay, formatMonthYear,
		isoWeekNumber, localDateStr,

        time24h

	} from '$lib/dateUtils';
	import DayPreviewPopup from './DayPreviewPopup.svelte';
	import EventPopup from './EventPopup.svelte';
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
	const SHOW_WEEK_TOUCH_DEBUG = false;
	const WEEK_TOUCH_TARGET_WIDTH_REM = 4;
	const WEEK_NUMBER_GUTTER_REM = 1.8;
	const FIRST_WEEKDAY_CONTENT_INSET_REM = WEEK_TOUCH_TARGET_WIDTH_REM - WEEK_NUMBER_GUTTER_REM;
	const MONTH_CELL_NON_EVENT_PX = 47;
	const MONTH_EVENT_ROW_PX = 22;
	const MONTH_OVERFLOW_ROW_PX = 23;
	const MONTH_EVENT_ROW_GAP_PX = 3;

	let gridEl: HTMLElement;
	let cellHeight = 80;
	let ro: ResizeObserver;
	let previewDay: Date | null = null;
	let previewEvents: CalendarEvent[] = [];
	let previewAnchorRect: DOMRect | null = null;
	let popupEvent: CalendarEvent | null = null;
	const pullToRefresh = createPullToRefresh(() => refresh?.() ?? Promise.resolve());
	const swipe = createHorizontalSwipe(
		() => goToMonth(-1),
		() => goToMonth(1),
	);

	// Reserve vertical room for the overflow row itself so "+N more" stays visible.
	$: eventListBudgetPx = Math.max(0, cellHeight - MONTH_CELL_NON_EVENT_PX);
	$: overflowRowsVisible = 1 + Math.floor(
		Math.max(0, eventListBudgetPx + MONTH_EVENT_ROW_GAP_PX - MONTH_OVERFLOW_ROW_PX) /
		(MONTH_EVENT_ROW_PX + MONTH_EVENT_ROW_GAP_PX)
	);
	$: maxVisible = Math.max(1, Math.min(5, overflowRowsVisible));

	onMount(() => {
		ro = new ResizeObserver((entries) => {
			const rect = entries[0]?.contentRect;
			if (!rect) return;
			cellHeight = rect.height / 6;
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

	/**
	 * Groups the weather forecast timeseries by visible calendar day so each
	 * month cell can render its own noon-weather summary without extra lookups.
	 */
	function buildCells(cells: Date[], timeseries: TimeSeries[]): { day: Date; series: TimeSeries[] }[] {
		return cells.map((day) => {
			const key = localDateStr(day);
			return { day, series: timeseries.filter((ts) => localDateStr(new Date(ts.time)) === key) };
		});
	}

	$: cellsWithWeather = buildCells(cells, timeseries);
	$: {
		const activePreviewDay = previewDay;
		if (activePreviewDay && !cells.some((cell) => isSameDay(cell, activePreviewDay))) {
			closeDayPreview();
		}
	}

	function closeDayPreview() {
		previewDay = null;
		previewEvents = [];
		previewAnchorRect = null;
	}

	function goToMonth(offset: number) {
		closeDayPreview();
		anchor = addMonths(anchor, offset);
	}

	function goToDay(day: Date) {
		closeDayPreview();
		anchor = day;
		currentView.set('day');
	}

	function onDayCellKeydown(event: KeyboardEvent, day: Date) {
		if (event.key !== 'Enter' && event.key !== ' ') return;
		event.preventDefault();
		goToDay(day);
	}

	/**
	 * Anchors the overflow preview to the clicked "+N more" control so the user
	 * keeps direct day navigation on the cell while getting a local event preview.
	 */
	function openDayPreview(day: Date, dayEvents: CalendarEvent[], event: MouseEvent) {
		event.stopPropagation();
		const target = event.currentTarget;
		if (!(target instanceof HTMLElement)) return;
		if (previewDay && isSameDay(previewDay, day)) {
			closeDayPreview();
			return;
		}
		previewDay = day;
		previewEvents = dayEvents;
		previewAnchorRect = target.getBoundingClientRect();
	}

	function openEventPopup(event: CustomEvent<{ event: CalendarEvent }>) {
		closeDayPreview();
		popupEvent = event.detail.event;
	}

	function shouldHandleCalendarKeys(event: KeyboardEvent): boolean {
		if (previewDay || popupEvent || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return false;
		const target = event.target;
		if (!(target instanceof HTMLElement)) return true;
		return !target.closest('input, textarea, select, [contenteditable="true"]');
	}

	function onWindowKeydown(event: KeyboardEvent) {
		if (!shouldHandleCalendarKeys(event)) return;
		if (event.key === 'ArrowLeft') {
			event.preventDefault();
			goToMonth(-1);
			return;
		}
		if (event.key === 'ArrowRight') {
			event.preventDefault();
			goToMonth(1);
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
			<button class="outline nav-btn" on:click={() => goToMonth(-1)}>‹</button>
		</div>
		<h2 class="period">{formatMonthYear(anchor)}</h2>
		<div class="header-right">
			{#if lastFetchedAt}
				<span class="updated">Updated {time24h(lastFetchedAt)}</span>
			{/if}
			{#if !isCurrentMonth}
				<button class="outline today-btn" on:click={() => { closeDayPreview(); anchor = new Date(); }}>Today</button>
			{/if}
			<button class="outline nav-btn" on:click={() => goToMonth(1)}>›</button>
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
					on:click={() => { closeDayPreview(); anchor = rowStart; currentView.set('week'); }}
					aria-label={`Open week ${isoWeekNumber(rowStart)}`}
				>
					<span class="week-num-label">{isoWeekNumber(rowStart)}</span>
				</button>
			</div>
			{#each cellsWithWeather.slice(rowIdx * 7, rowIdx * 7 + 7) as { day, series }, colIdx}
				{@const dayEvents = eventsOnDay(events, day)}
				{@const visible = dayEvents.length > maxVisible ? dayEvents.slice(0, maxVisible - 1) : dayEvents}
				{@const overflow = dayEvents.length - visible.length}
				<div
					class="cal-cell"
					class:first-weekday={colIdx === 0}
					class:other-month={day.getMonth() !== currentMonth}
					class:today={isSameDay(day, today)}
					role="button"
					tabindex="0"
					style:--first-weekday-content-inset={colIdx === 0 ? `${FIRST_WEEKDAY_CONTENT_INSET_REM}rem` : '0rem'}
					on:click={() => goToDay(day)}
					on:keydown={(event) => onDayCellKeydown(event, day)}
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
							<button
								type="button"
								class="overflow"
								on:click={(event) => openDayPreview(day, dayEvents, event)}
								aria-label={`Show ${overflow} more events for ${day.toLocaleDateString()}`}
							>
								+{overflow} more
							</button>
						{/if}
					</div>
				</div>
			{/each}
		{/each}
	</div>
</div>

<DayPreviewPopup
	day={previewDay}
	events={previewEvents}
	anchorRect={previewAnchorRect}
	on:close={closeDayPreview}
	on:openDay={() => previewDay && goToDay(previewDay)}
	on:openEvent={openEventPopup}
/>

<EventPopup event={popupEvent} on:close={() => (popupEvent = null)} />
<style>
	.month-view {
		--week-column-width: 1.8rem;
		--weekday-row-height: 1.8rem;
		--cell-padding-x: 0.4rem;
		--cell-padding-y: 0.3rem;
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
		grid-template-columns: var(--week-column-width) repeat(7, minmax(0, 1fr));
		align-items: stretch;
		min-height: var(--weekday-row-height);
		flex-shrink: 0;
		border-bottom: 1px solid var(--pico-muted-border-color);
	}

	.wnum-header {
		display: flex;
		align-items: center;
		justify-content: center;
		border-right: 1px solid var(--pico-muted-border-color);
	}

	.dow {
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.75rem;
		font-weight: 600;
		padding: 0.35rem 0;
		color: var(--pico-muted-color);
	}

	.cal-grid {
		flex: 1;
		display: grid;
		grid-template-columns: var(--week-column-width) repeat(7, minmax(0, 1fr));
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
		justify-content: center;
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
		width: var(--week-column-width);
		height: 100%;
		pointer-events: none;
	}

	.cal-cell {
		border-right: 1px solid var(--pico-muted-border-color);
		border-bottom: 1px solid var(--pico-muted-border-color);
		padding: var(--cell-padding-y) var(--cell-padding-x);
		width: 100%;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
		user-select: none;
	}

	.cal-cell:focus-visible {
		outline: 2px solid var(--pico-primary);
		outline-offset: -2px;
	}

	.cal-cell.first-weekday .event-list {
		padding-left: calc(var(--first-weekday-content-inset) - var(--cell-padding-x));
	}

	.cell-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		min-height: 1.25rem;
		flex-shrink: 0;
	}

	.cal-cell.other-month {
		opacity: 0.35;
	}

	.day-num {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.5rem;
		height: 1.5rem;
		font-size: 0.82rem;
		font-weight: 600;
		line-height: 1.15;
		flex-shrink: 0;
		border-radius: 50%;
	}

	.cal-cell.today .day-num {
		background: var(--pico-primary);
		color: var(--pico-primary-inverse);
	}

	.event-list {
		display: flex;
		flex: 1 1 auto;
		flex-direction: column;
		gap: 0.14rem;
		min-height: 0;
		padding-bottom: 0.1rem;
		overflow: hidden;
	}

	.ev-chip {
		display: flex;
		gap: 0;
		align-items: center;
		background-image: none;
		border-left: 2px solid rgba(0, 0, 0, 0.15);
		border-radius: 0.28rem;
		padding: 0.1rem 0.34rem;
		min-height: 1rem;
		font-size: 0.71rem;
		font-weight: 500;
		line-height: 1.2;
		overflow: hidden;
		white-space: nowrap;
	}

	.ev-title {
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.overflow {
		all: unset;
		display: inline-flex;
		align-items: center;
		align-self: flex-start;
		min-height: 1rem;
		font-size: 0.66rem;
		line-height: 1.2;
		color: var(--pico-muted-color);
		padding: 0.1rem 0.35rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--pico-muted-border-color) 45%, transparent);
		cursor: pointer;
	}

	.overflow:hover,
	.overflow:focus-visible {
		color: var(--pico-color);
	}
</style>
