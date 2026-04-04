<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { currentView, VALID_VIEWS, type View } from '$lib/stores';
	import { fetchEvents, fetchWeather } from '$lib/api';
	import type { CalendarEvent, WeatherRecord, TimeSeries } from '$lib/api';
	import { weatherDayKeyForLocalDay } from '$lib/dateUtils';
	import DayView from '$lib/components/DayView.svelte';
	import WeekView from '$lib/components/WeekView.svelte';
	import MonthView from '$lib/components/MonthView.svelte';
	import WeatherView from '$lib/components/WeatherView.svelte';
	import TodoView from '$lib/components/TodoView.svelte';

	const STALE_MS = 5 * 60 * 1000;
	const RANGE_COOLDOWN_MS = 30 * 1000;
	const WEATHER_STALE_MS = 60 * 60 * 1000;
	const ANCHOR_KEY = 'rpi-calendar-anchor';

	let events: CalendarEvent[] = [];
	let weather: WeatherRecord | null = null;
	let weatherByDay: Record<string, TimeSeries[]> = {};
	let wxDebug = false;
	let anchor = new Date();
	let loadError = '';
	let lastFetchedAt = 0;
	let lastRangeFetchAt = 0;
	let mounted = false;
	let weatherInterval: ReturnType<typeof setInterval> | null = null;
	let refreshInFlight = false;
	let refreshController: AbortController | null = null;

	// The date range currently covered by `events` (set after each fetch)
	let fetchedMin: Date | null = null;
	let fetchedMax: Date | null = null;

	function utcDateKey(d: Date): string {
		const y = d.getUTCFullYear();
		const m = String(d.getUTCMonth() + 1).padStart(2, '0');
		const day = String(d.getUTCDate()).padStart(2, '0');
		return `${y}-${m}-${day}`;
	}

	$: {
		const series = weather?.forecast?.properties?.timeseries ?? [];
		const map: Record<string, TimeSeries[]> = {};
		for (const ts of series) {
			const key = utcDateKey(new Date(ts.time));
			(map[key] ??= []).push(ts);
		}
		weatherByDay = map;
	}

	// (debug note) use the wxdebug overlay instead of console logging.

	function saveAnchor(d: Date) {
		if (!mounted) return;
		localStorage.setItem(ANCHOR_KEY, d.toISOString());
	}

	function loadAnchor(): Date {
		const stored = localStorage.getItem(ANCHOR_KEY);
		if (stored) {
			const d = new Date(stored);
			if (!isNaN(d.getTime())) return d;
		}
		return new Date();
	}

	function syncViewToUrl(v: View) {
		const url = new URL(window.location.href);
		url.searchParams.set('view', v);
		history.replaceState(null, '', url);
	}

	function readViewFromUrl(): View | null {
		const param = new URL(window.location.href).searchParams.get('view');
		wxDebug = new URL(window.location.href).searchParams.get('wxdebug') === '1';
		return VALID_VIEWS.includes(param as View) ? (param as View) : null;
	}

	$: wxTodayKey = weatherDayKeyForLocalDay(new Date());
	$: wxTodayLen = weatherByDay[wxTodayKey]?.length ?? 0;
	$: wxDays = Object.keys(weatherByDay).length;

	/** Merge new events into the existing array, deduplicating by id. */
	function mergeEvents(existing: CalendarEvent[], incoming: CalendarEvent[]): CalendarEvent[] {
		const map = new Map(existing.map((e) => [e.id, e]));
		for (const e of incoming) map.set(e.id, e);
		return [...map.values()].sort((a, b) => {
			const as = a.start.dateTime ?? a.start.date ?? '';
			const bs = b.start.dateTime ?? b.start.date ?? '';
			return as < bs ? -1 : as > bs ? 1 : 0;
		});
	}

	/** Return the date window that the current view + anchor needs to display. */
	function viewWindow(view: View, a: Date): { min: Date; max: Date } {
		const d = new Date(a);
		if (view === 'day') {
			const min = new Date(d.getFullYear(), d.getMonth(), d.getDate());
			const max = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1);
			return { min, max };
		}
		if (view === 'week') {
			// ISO week: Mon–Sun
			const dow = d.getDay();
			const diff = dow === 0 ? -6 : 1 - dow;
			const mon = new Date(d.getFullYear(), d.getMonth(), d.getDate() + diff);
			const sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 7);
			return { min: mon, max: sun };
		}
		// month view shows up to 6 weeks
		const monthStart = new Date(d.getFullYear(), d.getMonth(), 1);
		const dow2 = monthStart.getDay();
		const gridStart = new Date(monthStart.getFullYear(), monthStart.getMonth(), monthStart.getDate() - (dow2 === 0 ? 6 : dow2 - 1));
		const gridEnd = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + 42);
		return { min: gridStart, max: gridEnd };
	}

	async function refresh() {
		if (refreshInFlight) {
			refreshController?.abort();
		}
		refreshController = new AbortController();
		const { signal } = refreshController;
		refreshInFlight = true;
		refreshWeatherIfNeeded();
		try {
			events = await fetchEvents(undefined, undefined, signal);
			fetchedMin = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
			fetchedMax = new Date(Date.now() + 150 * 24 * 60 * 60 * 1000);
			lastFetchedAt = Date.now();
			lastRangeFetchAt = Date.now();
			loadError = '';
		} catch (e: unknown) {
			if ((e as { name?: string }).name === 'AbortError') return;
			if (!events.length) {
				loadError = e instanceof Error ? e.message : String(e);
			}
		} finally {
			refreshInFlight = false;
		}
	}

	async function refreshWeatherIfNeeded() {
		if (weather) {
			const age = Date.now() - new Date(weather.fetched_at).getTime();
			if (age < WEATHER_STALE_MS) return;
		}
		try {
			weather = await fetchWeather();
		} catch {
			// keep existing weather data
		}
	}

	/** Fetch a targeted range and merge results, only if outside current range and cooldown elapsed. */
	async function fetchRangeIfNeeded(view: View, a: Date) {
		const { min: needMin, max: needMax } = viewWindow(view, a);

		const outsideRange =
			!fetchedMin || !fetchedMax ||
			needMin < fetchedMin ||
			needMax > fetchedMax;

		if (!outsideRange) return;

		const now = Date.now();
		if (now - lastRangeFetchAt < RANGE_COOLDOWN_MS) return;
		lastRangeFetchAt = now;

		// Expand the fetch window: go ±3 months around the needed range to
		// avoid repeated fetches while browsing nearby months/weeks.
		const fetchMin = new Date(needMin.getFullYear(), needMin.getMonth() - 3, 1);
		const fetchMax = new Date(needMax.getFullYear(), needMax.getMonth() + 3 + 1, 1);

		try {
			const incoming = await fetchEvents(fetchMin, fetchMax);
			events = mergeEvents(events, incoming);
			if (!fetchedMin || fetchMin < fetchedMin) fetchedMin = fetchMin;
			if (!fetchedMax || fetchMax > fetchedMax) fetchedMax = fetchMax;
		} catch (e: unknown) {
			console.warn('Range fetch failed:', e);
		}
	}

	function onVisibilityChange() {
		if (document.visibilityState === 'visible' && Date.now() - lastFetchedAt > STALE_MS) {
			refresh();
		}
	}

	onMount(() => {
		const urlView = readViewFromUrl();
		if (urlView) currentView.set(urlView);

		anchor = loadAnchor();
		mounted = true;

		currentView.subscribe((v) => syncViewToUrl(v));

		refresh();
		weatherInterval = setInterval(refreshWeatherIfNeeded, 60 * 1000);
		document.addEventListener('visibilitychange', onVisibilityChange);
	});

	onDestroy(() => {
		document.removeEventListener('visibilitychange', onVisibilityChange);
		if (weatherInterval) clearInterval(weatherInterval);
		refreshController?.abort();
	});

	$: saveAnchor(anchor);
	$: if (mounted && anchor && lastFetchedAt > 0) fetchRangeIfNeeded($currentView, anchor);
</script>

{#if loadError}
	<div class="error-banner">{loadError}</div>
{/if}

{#if wxDebug}
	<div class="wx-debug">
		<div><strong>wx</strong></div>
		<div>weather: {weather ? 'yes' : 'no'}</div>
		<div>fetched_at: {weather?.fetched_at ?? '-'}</div>
		<div>weatherByDay keys: {wxDays}</div>
		<div>today key: {wxTodayKey} ({wxTodayLen})</div>
		<div>sample keys: {Object.keys(weatherByDay).slice(0, 3).join(', ')}</div>
	</div>
{/if}

{#if $currentView === 'day'}
	<DayView {events} {weather} bind:anchor />
{:else if $currentView === 'week'}
	<WeekView {events} {weather} {weatherByDay} bind:anchor />
{:else if $currentView === 'month'}
	<MonthView {events} {weather} {weatherByDay} bind:anchor />
{:else if $currentView === 'weather'}
	<WeatherView {weather} />
{:else if $currentView === 'todo'}
	<TodoView />
{/if}

<style>
	.error-banner {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		background: var(--pico-del-color);
		color: white;
		text-align: center;
		padding: 0.5rem;
		font-size: 0.85rem;
		z-index: 200;
	}

	.wx-debug {
		position: fixed;
		bottom: 0.5rem;
		left: 0.5rem;
		background: rgba(0, 0, 0, 0.75);
		color: white;
		padding: 0.4rem 0.5rem;
		border-radius: 0.4rem;
		font-size: 0.75rem;
		z-index: 300;
		line-height: 1.25;
	}
</style>
