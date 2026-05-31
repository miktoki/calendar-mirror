<script lang="ts">
	import type { CounterState, TodoList } from '$lib/api';

	type CounterButton = {
		label: string;
		delta: number;
		disabled: boolean;
	};

	export let list: TodoList;
	export let state: CounterState | null = null;
	export let error = '';
	export let resetNote = '';
	export let buttons: CounterButton[] = [];
	export let todayLabel = '0';
	export let onDelta: ((delta: number) => void) | undefined = undefined;
	export let onHide: (() => void) | undefined = undefined;
</script>

<section class="counter-panel">
	<header class="panel-header">
		<div>
			<div class="panel-title">{list.name}</div>
			{#if resetNote}
				<div class="panel-note">{resetNote}</div>
			{/if}
		</div>
		<button type="button" class="outline panel-close" on:click={() => onHide?.()} aria-label="Hide panel">✕</button>
	</header>

	{#if state}
		<div class="counter-card">
			<div class="counter-value">{state.value}</div>
			<div class="counter-sub">today: {todayLabel}</div>
			<div class="counter-buttons">
				{#each buttons as button}
					<button class="outline" disabled={button.disabled} on:click={() => onDelta?.(button.delta)}>{button.label}</button>
				{/each}
			</div>
		</div>
	{:else if error}
		<p class="empty">{error}</p>
	{:else}
		<p class="empty">Loading counter…</p>
	{/if}
</section>

<style>
	.counter-panel {
		border: 1px solid var(--pico-muted-border-color);
		border-radius: 0.75rem;
		padding: 0.65rem 0.8rem;
		min-height: 11.5rem;
		display: flex;
		flex-direction: column;
		background: color-mix(in srgb, var(--pico-muted-border-color) 6%, transparent);
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		padding-bottom: 0.4rem;
		margin-bottom: 0.4rem;
		border-bottom: 1px solid var(--pico-muted-border-color);
		flex-shrink: 0;
	}

	.panel-title {
		font-size: 0.92rem;
		font-weight: 650;
		opacity: 0.9;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.panel-note {
		font-size: 0.72rem;
		color: var(--pico-muted-color);
		line-height: 1.2;
		margin-top: 0.12rem;
	}

	.panel-close {
		padding: 0.15rem 0.4rem;
		font-size: 0.85rem;
		line-height: 1;
		opacity: 0.8;
	}

	.counter-card {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 0.5rem;
		flex: 1;
		padding: 0.4rem 0;
	}

	.counter-value {
		font-size: clamp(2rem, 4vw, 2.8rem);
		font-variant-numeric: tabular-nums;
		font-weight: 700;
		line-height: 1;
	}

	.counter-sub {
		font-size: 0.8rem;
		opacity: 0.7;
	}

	.counter-buttons {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.4rem;
	}

	.counter-buttons button {
		padding-inline: 0.5rem;
	}

	.empty {
		color: var(--pico-muted-color);
		font-size: 0.9rem;
		padding: 1rem 0;
	}
</style>