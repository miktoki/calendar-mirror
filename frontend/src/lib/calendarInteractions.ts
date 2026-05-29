const PULL_REFRESH_THRESHOLD_PX = 140;
const HORIZONTAL_SWIPE_THRESHOLD_PX = 72; // Minimum horizontal movement in pixels to trigger a swipe, ignoring small accidental movements.
const HORIZONTAL_SWIPE_DOMINANCE_RATIO = 2.0; // Horizontal movement must be at least this times greater than vertical movement to count as a horizontal swipe.

export function isEditableTarget(target: EventTarget | null): boolean {
	return target instanceof HTMLElement && Boolean(target.closest('input, textarea, select, button, a, [contenteditable="true"]'));
}

export function defaultHourScrollTop(
	startHour: number,
	preferredStartHour: number,
	preferredEndHour: number,
	endHour: number,
	hourHeight: number,
	containerHeight: number,
): number {
	const totalVisibleHours = endHour - startHour + 1;
	const preferredVisibleHours = Math.max(0, preferredEndHour - preferredStartHour);
	const viewportHours = Math.max(0, containerHeight / hourHeight);
	const extraHours = Math.max(0, viewportHours - preferredVisibleHours);
	const earlyEveningHours = Math.min(2, extraHours);
	const morningHours = Math.min(2, Math.max(0, extraHours - earlyEveningHours));
	const topHour = preferredStartHour - morningHours;
	const maxTopHour = Math.max(startHour, startHour + totalVisibleHours - viewportHours);
	const clampedTopHour = Math.min(Math.max(startHour, topHour), maxTopHour);
	return Math.max(0, (clampedTopHour - startHour) * hourHeight);
}

export function scrollHoursBy(container: HTMLElement, hours: number, hourHeight: number) {
	container.scrollBy({ top: hours * hourHeight, behavior: 'smooth' });
}

export function createPullToRefresh(onRefresh?: () => Promise<void>) {
	let startY: number | null = null;
	let armed = false;
	let fired = false;

	async function triggerRefresh() {
		if (!onRefresh || fired) return;
		fired = true;
		try {
			await onRefresh();
		} finally {
			startY = null;
			armed = false;
			fired = false;
		}
	}

	function onTouchStart(event: TouchEvent, scrollTop: number) {
		if (!onRefresh || isEditableTarget(event.target)) return;
		startY = event.touches[0]?.clientY ?? null;
		armed = scrollTop <= 0;
		fired = false;
	}

	function onTouchMove(event: TouchEvent, scrollTop: number) {
		if (startY === null || !armed || fired) return;
		if (scrollTop > 0) {
			armed = false;
			return;
		}
		const currentY = event.touches[0]?.clientY ?? startY;
		if (currentY - startY >= PULL_REFRESH_THRESHOLD_PX) {
			void triggerRefresh();
		}
	}

	function onTouchEnd() {
		if (!fired) {
			startY = null;
			armed = false;
		}
	}

	return {
		onTouchStart,
		onTouchMove,
		onTouchEnd,
	};
}

/** Trigger previous/next navigation on deliberate horizontal swipe gestures. */
export function createHorizontalSwipe(onPrev?: () => void, onNext?: () => void) {
	let startX: number | null = null;
	let startY: number | null = null;
	let fired = false;

	function onTouchStart(event: TouchEvent) {
		if ((!onPrev && !onNext) || isEditableTarget(event.target)) return;
		startX = event.touches[0]?.clientX ?? null;
		startY = event.touches[0]?.clientY ?? null;
		fired = false;
	}

	function onTouchMove(event: TouchEvent) {
		if (startX === null || startY === null || fired) return;
		const currentX = event.touches[0]?.clientX ?? startX;
		const currentY = event.touches[0]?.clientY ?? startY;
		const deltaX = currentX - startX;
		const deltaY = currentY - startY;
		if (Math.abs(deltaX) < HORIZONTAL_SWIPE_THRESHOLD_PX) return;
		if (Math.abs(deltaX) <= Math.abs(deltaY) * HORIZONTAL_SWIPE_DOMINANCE_RATIO) return;
		fired = true;
		if (deltaX > 0) {
			onPrev?.();
			return;
		}
		onNext?.();
	}

	function onTouchEnd() {
		startX = null;
		startY = null;
		fired = false;
	}

	return {
		onTouchStart,
		onTouchMove,
		onTouchEnd,
	};
}