<script lang="ts">
  import TimedEventChip from '../src/lib/components/TimedEventChip.svelte';

  const endText = 'Ends soon';
  function openPopup() {}
</script>

<TimedEventChip endText={endText} onOpen={openPopup}></TimedEventChip>
