<script lang="ts">
	import type { CalendarEvent } from '$lib/api';
	import { eventColor } from '$lib/api';
	import {
		eventEnd,
		eventStart,
		formatDate,
		formatTime,
		isAllDay,
		isSameDay,
		plainTextFromHtml,
	} from '$lib/dateUtils';
	import { createEventDispatcher, onMount, tick } from 'svelte';

	export let day: Date | null = null;
	export let events: CalendarEvent[] = [];
	export let anchorRect: DOMRect | null = null;

	const dispatch = createEventDispatcher<{
		close: void;
		openDay: void;
		openEvent: { event: CalendarEvent };
	}>();

	let popupEl: HTMLDivElement;
	let popupStyle = 'top: 1rem; left: 1rem; max-height: calc(100vh - 1rem);';

	function close() {
		dispatch('close');
	}

	function openDay() {
		dispatch('openDay');
	}

	function openEvent(ev: CalendarEvent) {
		dispatch('openEvent', { event: ev });
	}

	function eventTimeLabel(ev: CalendarEvent): string {
		if (isAllDay(ev)) return 'All day';
		const start = eventStart(ev);
		const end = eventEnd(ev);
		if (isSameDay(start, end)) return `${formatTime(start)} - ${formatTime(end)}`;
		return `${formatDate(start)} ${formatTime(start)} - ${formatDate(end)} ${formatTime(end)}`;
	}

	$: eventCards = events.map((ev) => ({
		ev,
		color: eventColor(ev),
		timeLabel: eventTimeLabel(ev),
		description: plainTextFromHtml(ev.description),
	}));

	/**
	 * Keeps the popup top-aligned in the viewport while shifting it horizontally
	 * toward the clicked overflow affordance.
	 */
	async function updatePosition() {
		if (!day || !anchorRect || !popupEl) return;
		await tick();
		const margin = 10;
		const { innerWidth, innerHeight } = window;
		const rect = popupEl.getBoundingClientRect();
		const anchorMidX = anchorRect.left + anchorRect.width / 2;
		let left = anchorMidX - rect.width / 2;
		const maxHeight = Math.max(220, innerHeight - margin * 2);
		const top = margin;

		left = Math.min(Math.max(left, margin), Math.max(margin, innerWidth - rect.width - margin));

		popupStyle = `top: ${top}px; left: ${left}px; max-height: ${maxHeight}px;`;
	}

	function onWindowKeydown(event: KeyboardEvent) {
		if (!day || event.key !== 'Escape') return;
		event.preventDefault();
		close();
	}

	onMount(() => {
		const onResize = () => void updatePosition();
		window.addEventListener('resize', onResize);
		return () => window.removeEventListener('resize', onResize);
	});

	$: if (day && anchorRect && popupEl) {
		void updatePosition();
	}
</script>

<svelte:window on:keydown={onWindowKeydown} />

{#if day}
	<div class="preview-layer" role="presentation">
		<button type="button" class="preview-backdrop" on:click={close} aria-label="Close event preview"></button>
		<div
			bind:this={popupEl}
			class="preview-popup"
			role="dialog"
			aria-label={`Events for ${formatDate(day)}`}
			style={popupStyle}
		>
			<div class="preview-header">
				<button type="button" class="preview-day-link" on:click={openDay}>
					<span class="preview-day-label">{formatDate(day)}</span>
					<span class="preview-day-count">{events.length} {events.length === 1 ? 'event' : 'events'}</span>
				</button>
				<button type="button" class="close-btn" on:click={close} aria-label="Close">✕</button>
			</div>

			<div class="preview-events">
				{#each eventCards as item}
					<button
						type="button"
						class="preview-event"
						style={`--event-bg: ${item.color.bg}; --event-fg: ${item.color.fg};`}
						on:click={() => openEvent(item.ev)}
					>
						<span class="preview-event-time">{item.timeLabel}</span>
						<span class="preview-event-title">{item.ev.summary}</span>
						{#if item.description}
							<span class="preview-event-description">{item.description}</span>
						{/if}
					</button>
				{/each}
			</div>
		</div>
	</div>
{/if}

<style>
	.preview-layer {
		position: fixed;
		inset: 0;
		pointer-events: auto;
		z-index: 450;
	}

	.preview-backdrop {
		all: unset;
		position: absolute;
		inset: 0;
		cursor: default;
		background: rgba(10, 14, 24, 0.14);
		backdrop-filter: blur(7px);
	}

	.preview-popup {
		position: fixed;
		pointer-events: auto;
		width: min(22rem, calc(100vw - 1rem));
		min-height: min(18rem, calc(100vh - 1.25rem));
		display: flex;
		flex-direction: column;
		background: color-mix(in srgb, var(--pico-background-color) 96%, black);
		border: 1px solid var(--pico-muted-border-color);
		border-radius: 0.9rem;
		box-shadow: 0 18px 40px rgba(0, 0, 0, 0.38);
		overflow: hidden;
		backdrop-filter: blur(10px);
	}

	.preview-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.85rem 0.95rem 0.7rem;
		border-bottom: 1px solid var(--pico-muted-border-color);
	}

	.preview-day-link {
		all: unset;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		cursor: pointer;
	}

	.preview-day-label {
		font-size: 1rem;
		font-weight: 700;
		line-height: 1.2;
	}

	.preview-day-count {
		font-size: 0.75rem;
		color: var(--pico-muted-color);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--pico-muted-color);
		cursor: pointer;
		font-size: 0.9rem;
		line-height: 1;
		padding: 0.15rem;
		flex-shrink: 0;
	}

	.preview-events {
		display: flex;
		flex: 1 1 auto;
		flex-direction: column;
		gap: 0.35rem;
		min-height: 0;
		padding: 0.75rem;
		overflow-y: auto;
	}

	.preview-event {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.12rem;
		padding: 0.55rem 0.65rem 0.6rem;
		border: 0;
		border-left: 0.35rem solid var(--event-bg);
		border-radius: 0.55rem;
		background: color-mix(in srgb, var(--event-bg) 22%, var(--pico-card-background-color));
		color: inherit;
		text-align: left;
		cursor: pointer;
	}

	.preview-event-time {
		font-size: 0.68rem;
		font-weight: 700;
		line-height: 1.2;
		color: color-mix(in srgb, var(--event-fg) 65%, var(--pico-muted-color));
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}

	.preview-event-title {
		font-size: 0.92rem;
		font-weight: 600;
		line-height: 1.25;
	}

	.preview-event-description {
		font-size: 0.8rem;
		line-height: 1.35;
		color: var(--pico-muted-color);
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		overflow: hidden;
	}

</style>