<script lang="ts">
	import type { CalendarEvent } from '$lib/api';
	import { formatTime, formatDate, eventStart, eventEnd, isAllDay } from '$lib/dateUtils';
	import { createEventDispatcher } from 'svelte';

	export let event: CalendarEvent | null = null;

	const dispatch = createEventDispatcher<{ close: void }>();

	function close() {
		dispatch('close');
	}

	function onBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) close();
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}

	$: start = event ? eventStart(event) : null;
	$: end = event ? eventEnd(event) : null;
	$: allDay = event ? isAllDay(event) : false;
</script>

<svelte:window on:keydown={onKeydown} />

{#if event}
	<div class="backdrop" on:click={onBackdropClick}>
		<div class="popup">
			<div class="popup-header">
				<span class="popup-title">{event.summary}</span>
				<button class="close-btn" on:click={close} aria-label="Close">✕</button>
			</div>
			<div class="popup-body">
				<div class="detail-row">
					<span class="detail-label">Date</span>
					<span>{start ? formatDate(start) : ''}</span>
				</div>
				{#if !allDay && start && end}
					<div class="detail-row">
						<span class="detail-label">Time</span>
						<span>{formatTime(start)} – {formatTime(end)}</span>
					</div>
				{/if}
				{#if event.location}
					<div class="detail-row">
						<span class="detail-label">Where</span>
						<span>{event.location}</span>
					</div>
				{/if}
				{#if event.description}
					<div class="detail-row description">
						<span class="detail-label">Notes</span>
						<div class="description-text">{@html event.description}</div>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 500;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(0, 0, 0, 0.35);
	}

	.popup {
		background: var(--pico-background-color);
		border: 1px solid var(--pico-muted-border-color);
		border-radius: 0.5rem;
		min-width: 18rem;
		max-width: min(90vw, 28rem);
		max-height: 80vh;
		overflow-y: auto;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
	}

	.popup-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.8rem 1rem 0.5rem;
		border-bottom: 1px solid var(--pico-muted-border-color);
	}

	.popup-title {
		font-weight: 600;
		font-size: 1rem;
		line-height: 1.3;
	}

	.close-btn {
		background: none;
		border: none;
		cursor: pointer;
		color: var(--pico-muted-color);
		font-size: 0.85rem;
		padding: 0.1rem 0.2rem;
		flex-shrink: 0;
		line-height: 1;
	}

	.close-btn:hover {
		color: var(--pico-color);
	}

	.popup-body {
		padding: 0.6rem 1rem 0.8rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.detail-row {
		display: flex;
		gap: 0.75rem;
		font-size: 0.875rem;
		align-items: baseline;
	}

	.detail-label {
		color: var(--pico-muted-color);
		font-size: 0.75rem;
		min-width: 3rem;
		flex-shrink: 0;
	}

	.description-text {
		word-break: break-word;
		font-size: 0.85rem;
		line-height: 1.5;
	}

	.description-text :global(a) {
		color: var(--pico-primary);
	}

	.description-text :global(b),
	.description-text :global(strong) {
		font-weight: 600;
	}

	.description-text :global(i),
	.description-text :global(em) {
		font-style: italic;
	}

	.description-text :global(ul),
	.description-text :global(ol) {
		padding-left: 1.2rem;
		margin: 0.25rem 0;
	}

	.description-text :global(p) {
		margin: 0.2rem 0;
	}

	.description-text :global(br) {
		display: block;
		content: '';
		margin-top: 0.2rem;
	}
</style>
