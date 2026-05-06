const PULL_REFRESH_THRESHOLD_PX = 140;

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