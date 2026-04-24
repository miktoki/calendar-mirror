<script lang="ts">
	import type { CalendarEvent } from '$lib/api';
	import { eventColor } from '$lib/api';

	export let event: CalendarEvent;
	export let density: 'day' | 'week' = 'day';
	export let onOpen: ((event: CalendarEvent) => void) | undefined = undefined;

	$: color = eventColor(event);

	function open() {
		onOpen?.(event);
	}
</script>

<button
	type="button"
	class="chip"
	class:compact={density === 'week'}
	style="background: {color.bg}; color: {color.fg};"
	on:click|stopPropagation={open}
>
	{event.summary}
</button>

<style>
	.chip {
		all: unset;
		box-sizing: border-box;
		display: inline-block;
		background-image: none;
		border-radius: 0.3rem;
		padding: 0.15rem 0.5rem;
		font-size: 0.8rem;
		line-height: 1.2;
		font: inherit;
		cursor: pointer;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 100%;
		text-align: left;
	}

	.chip.compact {
		display: block;
		width: 100%;
		border-left: 2px solid rgba(0, 0, 0, 0.15);
		border-radius: 0.2rem;
		padding: 0.02rem 0.3rem;
		font-size: 0.68rem;
		line-height: 1.4;
	}
</style>