<script lang="ts">
	import type { TimeSeries } from '$lib/api';
	import { wxIconUrl } from '$lib/wxIcons';

	export let series: TimeSeries[] = [];
	export let hour: number | null = null;
	export let mode: 'hour' | 'day' = 'hour';
	// NOTE: `ts.time` is an ISO string with 'Z' (UTC). We match `hour` against UTC hours.

	function closest(list: TimeSeries[], h: number | null): TimeSeries | null {
		if (!list.length) return null;
		const sorted = [...list].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
		if (h === null) return sorted[0] ?? null;
		const hourOf = (ts: TimeSeries) => new Date(ts.time).getUTCHours();
		const exact = sorted.find((ts) => hourOf(ts) === h);
		if (exact) return exact;
		return sorted.reduce((best, cur) => {
			const bestScore = Math.abs(hourOf(best) - h);
			const curScore = Math.abs(hourOf(cur) - h);
			if (curScore !== bestScore) return curScore < bestScore ? cur : best;
			// tie-break: prefer later entry so we don't pick "yesterday's" late hour
			return new Date(cur.time).getTime() > new Date(best.time).getTime() ? cur : best;
		});
	}

	function symbol(ts: TimeSeries): string {
		return (
			ts.data.next_1_hours?.summary.symbol_code ??
			ts.data.next_6_hours?.summary.symbol_code ??
			ts.data.next_12_hours?.summary.symbol_code ??
			''
		);
	}

	function temp(ts: TimeSeries): string {
		const t = ts.data.instant.details['air_temperature'];
		return t !== undefined ? `${Math.round(t)}°` : '';
	}

	function precip(ts: TimeSeries): string {
		const p =
			ts.data.next_1_hours?.details?.['precipitation_amount'] ??
			ts.data.next_6_hours?.details?.['precipitation_amount'] ??
			ts.data.next_12_hours?.details?.['precipitation_amount'];
		if (p === undefined || p === null) return '';
		if (typeof p !== 'number' || !isFinite(p)) return '';
		// Keep it compact. Most values are < 10mm.
		if (p <= 0) return '';
		return `${p.toFixed(p < 10 ? 1 : 0)}mm`;
	}

	function dayPrecipTotal(list: TimeSeries[]): string {
		let sum = 0;
		for (const ts of list) {
			const p = ts.data.next_1_hours?.details?.['precipitation_amount'];
			if (typeof p === 'number' && isFinite(p)) sum += p;
		}
		if (sum <= 0) return '';
		return `${sum.toFixed(sum < 10 ? 1 : 0)}mm`;
	}

	$: entry = closest(series, hour);
	$: sym = entry ? symbol(entry) : '';
	$: iconUrl = sym ? wxIconUrl(sym) : null;
	$: tmp = entry ? temp(entry) : '';
	$: pr = mode === 'day' ? dayPrecipTotal(series) : (entry ? precip(entry) : '');
	$: hasContent = Boolean(iconUrl || tmp || pr);
</script>

{#if series?.length && hasContent}
	<span class="wx" class:wx-day={mode === 'day'}>
		{#if pr}<span class="wx-pr">{pr}</span>{/if}
		{#if iconUrl}
			<img src={iconUrl} alt={sym} class="wx-icon" />
		{/if}
		{#if tmp}<span class="wx-temp">{tmp}</span>{/if}
	</span>
{/if}


<style>
	.wx {
		display: inline-flex;
		align-items: center;
		gap: 0.15rem;
		opacity: 0.9;
		line-height: 1;
		flex-shrink: 0;
	}

	.wx-icon {
		opacity: 1;
		width: 1rem;
		height: 1rem;
		display: block;
	}

	.wx-day .wx-icon {
		width: 1.1rem;
		height: 1.1rem;
	}

	.wx-temp {
		font-size: 0.65rem;
		font-variant-numeric: tabular-nums;
		opacity: 0.75;
	}

	.wx-pr {
		font-size: 0.6rem;
		opacity: 0.7;
		font-variant-numeric: tabular-nums;
	}


	.wx-day .wx-temp {
		font-size: 0.7rem;
	}
</style>
