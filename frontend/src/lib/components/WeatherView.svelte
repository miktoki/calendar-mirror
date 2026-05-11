<script lang="ts">
	import type { WeatherRecord, TimeSeries } from '$lib/api';
	import { rebootServer, refreshWeather } from '$lib/api';
	import { wxIconUrl } from '$lib/wxIcons';
	import { longpress } from '$lib/longpress';

	export let weather: WeatherRecord | null;

	let refreshing = false;
	let error = '';

	/** Refresh the weather data and reload the page. */
	async function doRefresh() {
		refreshing = true;
		error = '';
		try {
			await refreshWeather();
			location.reload();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			refreshing = false;
		}
	}
	async function placeholder() {
		
	}
	/** Convert a weather symbol code to a human-readable label. */
	function symbolLabel(code: string): string {
		return code.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
	}

	/** Format an ISO string to a human-readable hour. */
	function formatHour(iso: string): string {
		return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
	}

	/** Format an ISO string to a human-readable day label. */
	function formatDayLabel(iso: string): string {
		return new Date(iso).toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
	}

	interface DayGroup {
		label: string;
		date: string;
		entries: TimeSeries[];
	}

	$: days = groupByDay(weather?.forecast?.properties?.timeseries ?? []);

	/** Group time series entries by day, filtering out nighttime hours. */
	function groupByDay(series: TimeSeries[]): DayGroup[] {
		const map = new Map<string, TimeSeries[]>();
		for (const ts of series) {
			const h = new Date(ts.time).getHours();
			if (h < 6 || h > 20) continue;
			const d = ts.time.slice(0, 10);
			if (!map.has(d)) map.set(d, []);
			map.get(d)!.push(ts);
		}
		const groups: DayGroup[] = [];
		for (const [date, entries] of map) {
			groups.push({ label: formatDayLabel(date + 'T12:00:00'), date, entries });
		}
		return groups.slice(0, 7);
	}

	/** Get the most relevant weather symbol code for a time series entry. */
	function getSymbol(ts: TimeSeries): string {
		return (
			ts.data.next_1_hours?.summary.symbol_code ??
			ts.data.next_6_hours?.summary.symbol_code ??
			ts.data.next_12_hours?.summary.symbol_code ??
			''
		);
	}

	/** Get the air temperature for a time series entry. */
	function getTemp(ts: TimeSeries): number | null {
		const t = ts.data.instant.details['air_temperature'];
		return t !== undefined ? Math.round(t) : null;
	}

	/** Get the precipitation amount for a time series entry. */
	function getRain(ts: TimeSeries): number | null {
		const r =
			ts.data.next_1_hours?.details['precipitation_amount'] ??
			ts.data.next_6_hours?.details['precipitation_amount'] ??
			null;
		return r !== null ? Math.round(r * 10) / 10 : null;
	}

	/** Get the icon URL for a weather symbol code. */
	function iconUrl(code: string): string | null {
		return wxIconUrl(code);
	}

</script>

<div class="weather-view">
	<header class="weather-header">
		<h2>Weather Forecast</h2>
		<div class="header-right">
			{#if weather}
				<span class="updated">Updated {new Date(weather.fetched_at).toLocaleString()}</span>
			{/if}
			<button class="outline" on:click={doRefresh} disabled={refreshing}>
				{refreshing ? 'Refreshing…' : '↻ Refresh'}
			</button>
			<button class="outline" on:click={rebootServer}>
				{'⏻ Reboot'}
			</button>
		</div>
	</header>

	{#if error}
		<p class="error">{error}</p>
	{/if}

	{#if !weather}
		<div class="empty">
			<p>No forecast data. Press Refresh to fetch.</p>
		</div>
	{:else}
		<div class="days-scroll">
			{#each days as group}
				<section class="day-section">
					<h3 class="day-label">{group.label}</h3>
					<div class="hours-row">
						{#each group.entries as ts}
							{@const temp = getTemp(ts)}
							{@const symbol = getSymbol(ts)}
							{@const rain = getRain(ts)}
							<div class="hour-card">
								<span class="hour">{formatHour(ts.time)}</span>
								{#if symbol && iconUrl(symbol)}
									<img
										class="wx-icon"
										src={iconUrl(symbol)}
										alt={symbolLabel(symbol)}
										title={symbolLabel(symbol)}
									/>
								{/if}
								<span class="temp">{temp !== null ? `${temp}°` : '—'}</span>
								{#if rain !== null && rain > 0}
									<span class="rain">💧{rain}mm</span>
								{/if}
							</div>
						{/each}
					</div>
				</section>
			{/each}
		</div>
	{/if}
</div>

<style>
	.weather-view {
		display: flex;
		flex-direction: column;
		height: 100vh;
		overflow: hidden;
	}

	.weather-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 1rem;
		flex-shrink: 0;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.weather-header h2 {
		margin: 0;
		font-size: 1.2rem;
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.updated {
		font-size: 0.75rem;
		color: var(--pico-muted-color);
	}

	.error {
		color: var(--pico-del-color);
		padding: 0.5rem 1rem;
	}

	.empty {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.days-scroll {
		flex: 1;
		overflow-y: auto;
		padding: 0.5rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.day-section {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.day-label {
		font-size: 0.9rem;
		font-weight: 700;
		margin: 0;
		color: var(--pico-muted-color);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.hours-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.hour-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		background: var(--pico-card-background-color);
		border: 1px solid var(--pico-muted-border-color);
		border-radius: 0.5rem;
		padding: 0.4rem 0.5rem;
		min-width: 4rem;
		gap: 0.15rem;
	}

	.hour {
		font-size: 0.7rem;
		color: var(--pico-muted-color);
	}

	.wx-icon {
		width: 2rem;
		height: 2rem;
	}

	.temp {
		font-size: 1rem;
		font-weight: 600;
	}

	.rain {
		font-size: 0.65rem;
		color: var(--pico-color);
	}
</style>
