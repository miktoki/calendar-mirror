<script lang="ts">
	import type { CalendarEvent } from '$lib/api';
	import { eventColor } from '$lib/api';

	type TimedEventChipConfig = {
		startText: string;
		endText?: string | null;
		description?: string;
		compact?: boolean;
		narrow?: boolean;
		titleLines?: number;
		descriptionLines?: number;
		density?: 'day' | 'week';
		separatorColor?: string;
		style?: string;
	};

	export let event: CalendarEvent;
	export let config: TimedEventChipConfig;
	export let onOpen: ((event: CalendarEvent) => void) | undefined = undefined;

	$: startText = config.startText;
	$: endText = config.endText ?? null;
	$: description = config.description ?? '';
	$: compact = config.compact ?? false;
	$: narrow = config.narrow ?? false;
	$: titleLines = config.titleLines ?? 2;
	$: descriptionLines = config.descriptionLines ?? 0;
	$: density = config.density ?? 'day';
	$: separatorColor = config.separatorColor ?? 'transparent';
	$: style = config.style ?? '';
	$: color = eventColor(event);
	$: styleAttr = `${style}; background: ${color.bg}; color: ${color.fg}; --event-sep: ${separatorColor}; --title-lines: ${titleLines}; --desc-lines: ${descriptionLines};`;

	function open() {
		onOpen?.(event);
	}
</script>

<button
	type="button"
	class="event-block"
	class:compact
	class:narrow
	class:week={density === 'week'}
	style={styleAttr}
	on:click|stopPropagation={open}
>
	<div class="ev-meta-row">
		<span class="ev-time">{startText}</span>
		{#if endText != null}
			<span class="ev-time-sep">–</span>
			<span class="ev-time">{endText}</span>
		{/if}
		{#if compact}
			<strong class="ev-title">{event.summary}</strong>
		{/if}
	</div>
	{#if !compact}
		<strong class="ev-title">{event.summary}</strong>
	{/if}
	{#if descriptionLines > 0 && description}
		<span class="ev-notes">{description}</span>
	{/if}
</button>

<style>
	.event-block {
		all: unset;
		appearance: none;
		-moz-appearance: none;
		-webkit-appearance: none;
		position: absolute;
		box-sizing: border-box;
		display: flex;
		border: 0;
		border-left: 3px solid rgba(0, 0, 0, 0.15);
		border-bottom: 2px solid rgba(255, 255, 255, 0.35);
		border-radius: 0.4rem;
		background-image: none;
		box-shadow: none;
		font: inherit;
		margin: 0;
		padding: 0.25rem 0.45rem 0.3rem;
		padding-left: calc(0.5rem + 2px);
		padding-right: calc(0.5rem + 2px);
		overflow: hidden;
		font-size: 0.8rem;
		flex-direction: column;
		gap: 0.16rem;
		cursor: pointer;
		text-align: left;
	}

	.event-block.week {
		border-radius: 0.3rem;
		padding: 0.22rem 0.34rem 0.28rem;
		font-size: 0.72rem;
		gap: 0.14rem;
		margin-left: 1px;
		margin-right: 1px;
		border-bottom: 2px solid var(--event-sep, rgba(255, 255, 255, 0.35));
	}

	.event-block.compact {
		justify-content: center;
		padding-top: 0;
		padding-bottom: 0;
	}

	.ev-meta-row {
		display: flex;
		align-items: baseline;
		gap: 0.2rem;
		min-width: 0;
		flex: 0 0 auto;
		order: 1;
	}

	.event-block.week .ev-meta-row {
		gap: 0.18rem;
	}

	.ev-time,
	.ev-time-sep {
		font-size: 0.68rem;
		line-height: 1.1;
		opacity: 0.82;
		flex-shrink: 0;
	}

	.event-block.week .ev-time,
	.event-block.week .ev-time-sep {
		font-size: 0.65rem;
		opacity: 0.85;
	}

	.ev-title {
		font-size: 0.83rem;
		font-weight: 650;
		line-height: 1.15;
		min-width: 0;
		overflow: hidden;
	}

	.event-block.week .ev-title {
		font-size: 0.77rem;
	}

	.event-block.compact .ev-title {
		white-space: nowrap;
		text-overflow: ellipsis;
		flex: 1;
	}

	.event-block:not(.compact) .ev-title {
		order: 2;
		flex: 0 0 auto;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		line-clamp: var(--title-lines, 2);
		-webkit-line-clamp: var(--title-lines, 2);
		white-space: normal;
	}

	.ev-notes {
		order: 3;
		flex: 1 1 auto;
		min-height: 0;
		font-size: 0.68rem;
		line-height: 1.15;
		opacity: 0.78;
		overflow: hidden;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		line-clamp: var(--desc-lines, 2);
		-webkit-line-clamp: var(--desc-lines, 2);
		white-space: pre-line;
	}
</style>