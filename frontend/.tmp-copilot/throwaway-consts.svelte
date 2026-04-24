<script lang="ts">
  import TimedEventChip from '../src/lib/components/TimedEventChip.svelte';

  const event = { endText: 'Ends soon' };
  function openPopup() {}
</script>

{@const endText = event.endText}
{@const label = endText.toUpperCase()}
{@const ready = !!label}

{#if ready}
  <TimedEventChip endText={endText} onOpen={openPopup}></TimedEventChip>
{/if}
