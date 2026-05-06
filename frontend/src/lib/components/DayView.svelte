<script lang="ts">
	import type { CalendarEvent, WeatherRecord } from '$lib/api';
	import {
		eventStart, eventEnd, isAllDay, formatTime, formatDate,
		eventsOnDay, addDays, startOfDay, localDateStr, timedSegmentsForDay, layoutOverlappingSegments,
		timedEventChipContent, plainTextFromHtml
	} from '$lib/dateUtils';
	import WeatherWidget from './WeatherWidget.svelte';
	import { currentView } from '$lib/stores';
	import EventPopup from './EventPopup.svelte';
	import AllDayEventChip from './AllDayEventChip.svelte';
	import TimedEventChip from './TimedEventChip.svelte';
	import { createPullToRefresh, defaultHourScrollTop, isEditableTarget, scrollHoursBy } from '$lib/calendarInteractions';
	import { onMount } from 'svelte';

	export let events: CalendarEvent[];
	export let anchor: Date;
	export let weather: WeatherRecord | null = null;
	export let refresh: (() => Promise<void>) | undefined = undefined;

	let popupEvent: CalendarEvent | null = null;
	let scrollArea: HTMLDivElement;

	$: day = startOfDay(anchor);
	$: dayEvents = eventsOnDay(events, day);
	$: allSegments = timedSegmentsForDay(dayEvents, day, START_HOUR);
	$: fullDaySegments = allSegments.filter((s) => s.isFullDay);
	$: timedSegments = allSegments.filter((s) => !s.isFullDay);
	$: allDayEvents = dayEvents.filter((e) => isAllDay(e));
	$: layout = layoutOverlappingSegments(timedSegments);
	$: timedRender = timedSegments.map((segment) => {
		const height = heightPx(segment.displayStart, segment.displayEnd);
		const eventLayout = layout.get(segment.id);
		const chip = timedEventChipContent(height, eventLayout?.width ?? 1, Boolean(segment.ev.description), 'day');
		const description = plainTextFromHtml(segment.ev.description);
		const leftPct = (eventLayout?.left ?? 0) * 100;
		const widthPct = (eventLayout?.width ?? 1) * 100;
		const style = timedStyle(topPx(segment.displayStart), height, leftPct, widthPct);
		return {
			segment,
			config: timedChipConfig(segment, chip, description, style),
		};
	});

	const today = new Date();

	$: daySeries = (weather?.forecast?.properties?.timeseries ?? []).filter(
		(ts) => localDateStr(new Date(ts.time)) === localDateStr(day)
	);

	const HOUR_HEIGHT = 64;
	const START_HOUR = 6;
	const END_HOUR = 23;
	const DEFAULT_VISIBLE_START_HOUR = 8;
	const DEFAULT_VISIBLE_END_HOUR = 20;

	function topPx(start: Date): number {
		const minutes = start.getHours() * 60 + start.getMinutes() - START_HOUR * 60;
		return Math.max(0, (minutes / 60) * HOUR_HEIGHT);
	}

	function heightPx(start: Date, end: Date): number {
		const dur = (end.getTime() - start.getTime()) / 60000;
		return Math.max(20, (dur / 60) * HOUR_HEIGHT);
	}

	function openPopup(ev: CalendarEvent) {
		popupEvent = ev;
	}

	function timedStyle(top: number, height: number, leftPct: number, widthPct: number): string {
		return `top: ${top}px; height: ${height}px; left: ${leftPct}%; width: ${widthPct}%;`;
	}

	function timedChipConfig(
		segment: { ev: CalendarEvent; start: Date; end: Date; displayStart: Date; displayEnd: Date; isContinuation: boolean; endsAtMidnight: boolean },
		chip: ReturnType<typeof timedEventChipContent>,
		description: string,
		style: string,
	) {
		let startText: string;
		let endText: string | null;
		if (segment.isContinuation) {
			// Continuation day (day 2, day 3…): no start time shown, show end time with leading dash
			startText = '';
			endText = formatTime(segment.end);
		} else if (segment.endsAtMidnight) {
			// Starts here, runs to midnight: show start time with trailing dash
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
			density: 'day' as const,
			style,
		};
	}

	function timedRenderKey(item: { segment: { id: string } }, index: number): string {
		return `${item.segment.id}:${index}`;
	}

	const hours = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, i) => START_HOUR + i);

	$: isToday = day.toDateString() === today.toDateString();
	const pullToRefresh = createPullToRefresh(() => refresh?.() ?? Promise.resolve());

	onMount(() => {
		if (scrollArea) {
			scrollArea.scrollTop = defaultHourScrollTop(
				START_HOUR,
				DEFAULT_VISIBLE_START_HOUR,
				DEFAULT_VISIBLE_END_HOUR,
				END_HOUR,
				HOUR_HEIGHT,
				scrollArea.clientHeight,
			);
		}
	});

	function shouldHandleCalendarKeys(event: KeyboardEvent): boolean {
		if (popupEvent || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return false;
		const target = event.target;
		if (!(target instanceof HTMLElement)) return true;
		return !target.closest('input, textarea, select, [contenteditable="true"]');
	}

	function onWindowKeydown(event: KeyboardEvent) {
		if (!shouldHandleCalendarKeys(event)) return;
		if (scrollArea && event.key === 'PageDown') {
			event.preventDefault();
			scrollHoursBy(scrollArea, 3, HOUR_HEIGHT);
			return;
		}
		if (scrollArea && event.key === 'PageUp') {
			event.preventDefault();
			scrollHoursBy(scrollArea, -3, HOUR_HEIGHT);
			return;
		}
		if (scrollArea && event.key === 'Home' && !isEditableTarget(event.target)) {
			event.preventDefault();
			scrollArea.scrollTo({ top: 0, behavior: 'smooth' });
			return;
		}
		if (scrollArea && event.key === 'End' && !isEditableTarget(event.target)) {
			event.preventDefault();
			scrollArea.scrollTo({ top: scrollArea.scrollHeight, behavior: 'smooth' });
			return;
		}
		if (event.key === 'ArrowLeft') {
			event.preventDefault();
			anchor = addDays(anchor, -1);
			return;
		}
		if (event.key === 'ArrowRight') {
			event.preventDefault();
			anchor = addDays(anchor, 1);
			return;
		}
		if (event.key === 'ArrowUp') {
			event.preventDefault();
			currentView.set('week');
			return;
		}
	}
</script>

<svelte:window on:keydown={onWindowKeydown} />

<div class="day-view">
	<header class="day-header">
		<div class="header-left">
			<button class="outline nav-btn" on:click={() => (anchor = addDays(anchor, -1))}>‹</button>
		</div>
		<h2 class="nav-label" on:click={() => currentView.set('week')}>{formatDate(day)}</h2>
		<div class="header-right">
			{#if !isToday}
				<button class="outline today-btn" on:click={() => (anchor = new Date())}>Today</button>
			{/if}
			<button class="outline nav-btn" on:click={() => (anchor = addDays(anchor, 1))}>›</button>
		</div>
	</header>

	{#if allDayEvents.length || fullDaySegments.length}
		<div class="allday-row">
			{#each allDayEvents as ev}
				<AllDayEventChip event={ev} density="day" onOpen={openPopup} />
			{/each}
			{#each fullDaySegments as seg}
				<AllDayEventChip event={seg.ev} density="day" onOpen={openPopup} />
			{/each}
		</div>
	{/if}

	<div
		class="scroll-area"
		bind:this={scrollArea}
		on:touchstart={(event) => pullToRefresh.onTouchStart(event, scrollArea?.scrollTop ?? 0)}
		on:touchmove={(event) => pullToRefresh.onTouchMove(event, scrollArea?.scrollTop ?? 0)}
		on:touchend={pullToRefresh.onTouchEnd}
	>
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

			{#each timedRender as item, itemIdx (timedRenderKey(item, itemIdx))}
				<TimedEventChip
					event={item.segment.ev}
					config={item.config}
					onOpen={openPopup}
				></TimedEventChip>
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
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		padding: 0.5rem 1rem;
		flex-shrink: 0;
		gap: 0.5rem;
	}

	.day-header h2 {
		margin: 0;
		font-size: 1.2rem;
		text-align: center;
	}

	.header-left {
		display: flex;
		justify-content: flex-start;
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
		justify-content: flex-end;
		gap: 0.3rem;
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

</style>
