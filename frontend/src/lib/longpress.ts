interface LongpressParams {
  duration?: number;
  onClick?: () => void;
  onLongPress?: () => void;
  cancelOnMove?: boolean;
  moveThreshold?: number;
}

export function longpress(
  node: HTMLElement,
  { duration = 500, onClick, onLongPress, cancelOnMove = false, moveThreshold = 20 }: LongpressParams = {}
) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let startX = 0;
  let startY = 0;
  let fired = false;

  const start = (x: number, y: number) => {
    startX = x;
    startY = y;
    fired = false;

    timer = setTimeout(() => {
      timer = null;
      fired = true;
      onLongPress?.();
    }, duration);
  };

  const checkMove = (x: number, y: number) => {
    if (!cancelOnMove || !timer) return;
    const dx = Math.abs(x - startX);
    const dy = Math.abs(y - startY);
    if (dx > moveThreshold || dy > moveThreshold) {
      clearTimeout(timer);
      timer = null;
    }
  };

  const end = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
      if (!fired) onClick?.();
    }
    fired = false;
  };

  const cancel = () => {
    clearTimeout(timer ?? undefined);
    timer = null;
    fired = false;
  };

  // Mouse handlers
  const onMouseDown = (e: MouseEvent) => start(e.clientX, e.clientY);
  const onMouseMove = (e: MouseEvent) => checkMove(e.clientX, e.clientY);

  // Touch handlers
  const onTouchStart = (e: TouchEvent) => {
    const t = e.touches[0];
    start(t.clientX, t.clientY);
  };
  const onTouchMove = (e: TouchEvent) => {
    const t = e.touches[0];
    checkMove(t.clientX, t.clientY);
  };
  const onTouchEnd = (e: TouchEvent) => {
    // prevent the synthesized mouse click that follows touch
    e.preventDefault();
    end();
  };

  node.addEventListener('mousedown', onMouseDown);
  node.addEventListener('mousemove', onMouseMove);
  node.addEventListener('mouseup', end);
  node.addEventListener('mouseleave', cancel);

  node.addEventListener('touchstart', onTouchStart, { passive: true });
  node.addEventListener('touchmove', onTouchMove, { passive: true });
  node.addEventListener('touchend', onTouchEnd);   // not passive — calls preventDefault
  node.addEventListener('touchcancel', cancel);

  // node.style.userSelect = 'none';
  // node.style.webkitUserSelect = 'none';

  return {
    update(newParams: LongpressParams) {
      ({ duration = 500, onClick, onLongPress, cancelOnMove = false, moveThreshold = 20 } = newParams);
    },
    destroy() {
      node.removeEventListener('mousedown', onMouseDown);
      node.removeEventListener('mousemove', onMouseMove);
      node.removeEventListener('mouseup', end);
      node.removeEventListener('mouseleave', cancel);

      node.removeEventListener('touchstart', onTouchStart);
      node.removeEventListener('touchmove', onTouchMove);
      node.removeEventListener('touchend', onTouchEnd);
      node.removeEventListener('touchcancel', cancel);

      // node.style.userSelect = '';
      // node.style.webkitUserSelect = '';
    }
  };
}