<script lang="ts">
	import type { CalendarEvent, WeatherRecord, TimeSeries } from '$lib/api';
	import { eventColor } from '$lib/api';
	import {
		eventsOnDay, startOfMonth, startOfWeek, addDays, addMonths,
		isSameDay, formatMonthYear, isAllDay, eventStart, formatTime,
		isoWeekNumber, localDateStr
	} from '$lib/dateUtils';
	import WeatherWidget from './WeatherWidget.svelte';
	import { currentView } from '$lib/stores';
	import EventPopup from './EventPopup.svelte';
	import { onMount, onDestroy } from 'svelte';

	export let events: CalendarEvent[];
	export let anchor: Date;
	export let weather: WeatherRecord | null = null;

	let popupEvent: CalendarEvent | null = null;

	const today = new Date();
	const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
	const CELL_HEADER_PX = 20;
	const CHIP_PX = 11;
	const MAX_VISIBLE_ROWS = 6;

	let gridEl: HTMLElement;
	let cellHeight = 80;
	let ro: ResizeObserver;

	// Max chips that visually fit in a cell (no overflow line reserved yet;
	// per-cell logic in template reserves 1 slot for "+N more" when needed).
	$: maxVisible = Math.max(
		1,
		Math.min(MAX_VISIBLE_ROWS, Math.floor((cellHeight - CELL_HEADER_PX) / CHIP_PX))
	);

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
		if (popupEvent || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return false;
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

<div class="month-view">
	<header class="month-header">
		<button class="outline nav-btn" on:click={() => (anchor = addMonths(anchor, -1))}>‹</button>
		<span class="period">{formatMonthYear(anchor)}</span>
		<div class="header-right">
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
			<div
				class="week-num"
				on:click={() => { anchor = rowStart; currentView.set('week'); }}
			>{isoWeekNumber(rowStart)}</div>
			{#each cellsWithWeather.slice(rowIdx * 7, rowIdx * 7 + 7) as { day, series }}
				{@const dayEvents = eventsOnDay(events, day)}
				{@const visible = dayEvents.length > maxVisible ? dayEvents.slice(0, maxVisible - 1) : dayEvents}
				{@const overflow = dayEvents.length - visible.length}
				<div
					class="cal-cell"
					class:other-month={day.getMonth() !== currentMonth}
					class:today={isSameDay(day, today)}
					on:click={() => { anchor = day; currentView.set('day'); }}
				>
					<div class="cell-header">
						<span class="day-num">{day.getDate()}</span>
						<WeatherWidget {series} hour={12} mode="day" />
					</div>
					<div class="event-list">
						{#each visible as ev}
							{@const c = eventColor(ev)}
							<div class="ev-chip" style="background: {c.bg}; color: {c.fg};" on:click|stopPropagation={() => (popupEvent = ev)}>
								{#if !isAllDay(ev)}
									<span class="ev-time">{formatTime(eventStart(ev))}</span>
								{/if}
								<span class="ev-title">{ev.summary}</span>
							</div>
						{/each}
						{#if overflow > 0}
							<div class="overflow">+{overflow} more</div>
						{/if}
					</div>
				</div>
			{/each}
		{/each}
	</div>
</div>

<EventPopup event={popupEvent} on:close={() => (popupEvent = null)} />

<style>
	.month-view {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
	}

	.month-header {
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
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.6rem;
		color: var(--pico-muted-color);
		border-right: 1px solid var(--pico-muted-border-color);
		border-bottom: 1px solid var(--pico-muted-border-color);
		cursor: pointer;
		user-select: none;
	}

	.cal-cell {
		border-right: 1px solid var(--pico-muted-border-color);
		border-bottom: 1px solid var(--pico-muted-border-color);
		padding: 0.2rem 0.3rem;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		cursor: pointer;
		user-select: none;
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
		gap: 0.03rem;
		overflow: hidden;
	}

	.ev-chip {
		display: flex;
		gap: 0.16rem;
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
		cursor: pointer;
	}

	.ev-time {
		opacity: 0.8;
		flex-shrink: 0;
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
