"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import type {
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
} from "react";
import { useRouter } from "next/navigation";

/** A task in a reorderable list. Tasks are reordered within their selected day. */
export type ReorderableTask = {
  id: string;
  /** The list the task belongs to: its selected day, or null for the Backlog. */
  selectedDay: string | null;
  /**
   * When false the row can neither be dragged nor used as a drop anchor.
   * Flat lists use this to keep sub-tasks in place.
   */
  canReorder?: boolean;
};

type ItemDragProps = {
  draggable: boolean;
  "data-reorder-id": string;
  onDragStart: (event: DragEvent<HTMLElement>) => void;
  onDragEnd: (event: DragEvent<HTMLElement>) => void;
  onDragOver: (event: DragEvent<HTMLElement>) => void;
};

type ContainerDragProps = {
  onDragOver: (event: DragEvent<HTMLElement>) => void;
  onDrop: (event: DragEvent<HTMLElement>) => void;
};

/**
 * What the grip handle needs from its list: the mouse handlers that arm the
 * desktop drag, and the pointer handlers that drag the row directly on a
 * touchscreen.
 */
export type TaskDragHandleProps = {
  onMouseDown: (event: ReactMouseEvent<HTMLElement>) => void;
  onPointerDown: (event: ReactPointerEvent<HTMLElement>) => void;
  onPointerMove: (event: ReactPointerEvent<HTMLElement>) => void;
  onPointerUp: (event: ReactPointerEvent<HTMLElement>) => void;
  onPointerCancel: (event: ReactPointerEvent<HTMLElement>) => void;
  onContextMenu: (event: ReactMouseEvent<HTMLElement>) => void;
};

/** A finger holding a row's grip handle, tracked by pointer id. */
type TouchPress = {
  id: string;
  pointerId: number;
};

/** Distance from a viewport edge where a touch drag starts scrolling the page. */
const AUTOSCROLL_EDGE_PX = 72;
const AUTOSCROLL_STEP_PX = 12;

/** Move `draggedId` next to `overId`, before it or after it. */
function moveTo(
  order: string[],
  draggedId: string,
  overId: string,
  after: boolean,
): string[] {
  const currentIndex = order.indexOf(draggedId);
  const overIndex = order.indexOf(overId);
  if (currentIndex === -1 || overIndex === -1) return order;

  let insertAt = after ? overIndex + 1 : overIndex;
  if (currentIndex < insertAt) insertAt -= 1;
  if (insertAt === currentIndex) return order;

  const next = order.slice();
  next.splice(currentIndex, 1);
  next.splice(insertAt, 0, draggedId);
  return next;
}

function sameOrder(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((id, index) => id === b[index]);
}

/**
 * Drag-and-drop ordering for a task list. The list is reordered live while a
 * task is dragged by its handle, and the new order is saved through
 * `/api/tasks/reorder` on drop, then confirmed by refreshing the server data.
 *
 * Two gestures share that one path: the mouse drags with the native HTML5 drag
 * events the grip handle arms, and a finger or stylus drags with pointer
 * events, which is the only gesture touch browsers support. The pointer drag
 * tracks the row under the finger rather than the drag image, scrolls the page
 * when the finger reaches an edge, and leaves the rest of the row free to be
 * tapped and scrolled.
 *
 * Tasks can only move within their own selected day (or within the Backlog),
 * so dragging never changes a task's day by accident.
 */
export function useTaskReorder(items: ReorderableTask[]) {
  const router = useRouter();
  const [order, setOrder] = useState<string[]>(() => items.map((item) => item.id));
  const [armedId, setArmedId] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const orderRef = useRef(order);
  const itemsRef = useRef(items);
  const draggingRef = useRef<string | null>(null);
  const movedRef = useRef(false);
  const droppedRef = useRef(false);
  const busyRef = useRef(false);
  /** The finger currently holding a grip handle, if any. */
  const pressRef = useRef<TouchPress | null>(null);
  /** Suppresses the synthetic mouse events a touch fires after it lifts. */
  const touchGestureRef = useRef(false);

  useEffect(() => {
    itemsRef.current = items;
  });

  // Re-sync the visible order whenever fresh server data arrives, unless a
  // drag is in progress. Callers may pass a new array on every render, so the
  // state only changes when the sequence really differs.
  useEffect(() => {
    if (draggingRef.current) return;
    const ids = items.map((item) => item.id);
    if (!sameOrder(ids, orderRef.current)) {
      orderRef.current = ids;
      setOrder(ids);
    }
  }, [items]);

  // Releasing the press without starting a drag disarms the handle again.
  useEffect(() => {
    if (!armedId || draggingRef.current) return;
    const release = () => setArmedId(null);
    window.addEventListener("mouseup", release);
    return () => window.removeEventListener("mouseup", release);
  }, [armedId]);

  function applyOrder(next: string[]) {
    orderRef.current = next;
    setOrder(next);
  }

  function dayOf(id: string): string | null | undefined {
    return itemsRef.current.find((item) => item.id === id)?.selectedDay;
  }

  function canReorder(id: string): boolean {
    const item = itemsRef.current.find((entry) => entry.id === id);
    return item ? item.canReorder !== false : false;
  }

  async function persist(draggedId: string, orderedIds: string[]) {
    if (busyRef.current) return;
    busyRef.current = true;
    setError(null);

    const selectedDay = dayOf(draggedId) ?? null;
    const listIds = orderedIds.filter(
      (id) => canReorder(id) && (dayOf(id) ?? null) === selectedDay,
    );

    try {
      const response = await fetch("/api/tasks/reorder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_day: selectedDay, task_ids: listIds }),
      });
      const data = (await response.json()) as { error?: string };
      if (!response.ok) {
        throw new Error(data.error || "The new task order could not be saved.");
      }
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The new task order could not be saved.",
      );
      applyOrder(itemsRef.current.map((item) => item.id));
    } finally {
      busyRef.current = false;
    }
  }

  function handleDragStart(event: DragEvent<HTMLElement>, id: string) {
    draggingRef.current = id;
    setDraggingId(id);
    movedRef.current = false;
    droppedRef.current = false;
    setError(null);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", id);
  }

  // Dragging a task by its handle makes the containing card draggable.
  function handleHandleMouseDown(id: string) {
    // A touch press already owns the gesture; its synthetic mousedown must not
    // also arm the native drag.
    if (touchGestureRef.current) return;
    setArmedId(id);
  }

  /** The finger grabbed a grip handle: the row follows it from here. */
  function handleHandlePointerDown(
    event: ReactPointerEvent<HTMLElement>,
    id: string,
  ) {
    if (event.pointerType === "mouse" || !canReorder(id)) return;

    touchGestureRef.current = true;
    // Capture keeps the moves coming to the handle even as the list reorders
    // around the finger.
    event.currentTarget.setPointerCapture?.(event.pointerId);
    pressRef.current = { id, pointerId: event.pointerId };
    draggingRef.current = id;
    movedRef.current = false;
    droppedRef.current = false;
    setError(null);
    setArmedId(id);
    setDraggingId(id);
  }

  function handleHandlePointerMove(event: ReactPointerEvent<HTMLElement>) {
    const press = pressRef.current;
    if (!press || event.pointerId !== press.pointerId) return;

    const over = document
      .elementFromPoint(event.clientX, event.clientY)
      ?.closest<HTMLElement>("[data-reorder-id]");
    const overId = over?.dataset.reorderId;
    if (
      over &&
      overId &&
      overId !== press.id &&
      canReorder(overId) &&
      (dayOf(overId) ?? null) === (dayOf(press.id) ?? null)
    ) {
      const rect = over.getBoundingClientRect();
      const after = event.clientY > rect.top + rect.height / 2;
      const next = moveTo(orderRef.current, press.id, overId, after);
      if (next !== orderRef.current) {
        movedRef.current = true;
        applyOrder(next);
      }
    }

    // Held near an edge, the list keeps scrolling under the finger.
    if (event.clientY < AUTOSCROLL_EDGE_PX) {
      window.scrollBy(0, -AUTOSCROLL_STEP_PX);
    } else if (event.clientY > window.innerHeight - AUTOSCROLL_EDGE_PX) {
      window.scrollBy(0, AUTOSCROLL_STEP_PX);
    }
  }

  /** Release the touch gesture flags once the browser stops echoing them. */
  function releaseTouchGesture() {
    window.setTimeout(() => {
      touchGestureRef.current = false;
    }, 350);
  }

  function handleHandlePointerUp(event: ReactPointerEvent<HTMLElement>) {
    const press = pressRef.current;
    if (!press || event.pointerId !== press.pointerId) return;
    pressRef.current = null;
    releaseTouchGesture();
    draggingRef.current = null;
    setDraggingId(null);
    setArmedId(null);
    if (movedRef.current) {
      void persist(press.id, orderRef.current);
    }
    movedRef.current = false;
  }

  function handleHandlePointerCancel(event: ReactPointerEvent<HTMLElement>) {
    const press = pressRef.current;
    if (!press || event.pointerId !== press.pointerId) return;
    pressRef.current = null;
    releaseTouchGesture();
    draggingRef.current = null;
    setDraggingId(null);
    setArmedId(null);
    // A cancelled gesture puts the list back where the server last left it.
    if (movedRef.current) applyOrder(itemsRef.current.map((item) => item.id));
    movedRef.current = false;
  }

  // A long press on a grip handle should not open the browser's text menu.
  function handleHandleContextMenu(event: ReactMouseEvent<HTMLElement>) {
    if (!pressRef.current) return;
    event.preventDefault();
  }

  function handleItemDragOver(event: DragEvent<HTMLElement>, overId: string) {
    const draggedId = draggingRef.current;
    if (!draggedId || draggedId === overId) return;
    if (!canReorder(draggedId) || !canReorder(overId)) return;
    if ((dayOf(draggedId) ?? null) !== (dayOf(overId) ?? null)) return;

    event.preventDefault();
    event.dataTransfer.dropEffect = "move";

    const rect = event.currentTarget.getBoundingClientRect();
    const after = event.clientY > rect.top + rect.height / 2;
    const next = moveTo(orderRef.current, draggedId, overId, after);
    if (next !== orderRef.current) {
      movedRef.current = true;
      applyOrder(next);
    }
  }

  function handleItemDragEnd() {
    const draggedId = draggingRef.current;
    draggingRef.current = null;
    setDraggingId(null);
    setArmedId(null);
    // A drag released outside a drop target falls back to the saved order.
    if (draggedId && !droppedRef.current && movedRef.current) {
      applyOrder(itemsRef.current.map((item) => item.id));
    }
    movedRef.current = false;
  }

  function handleContainerDragOver(event: DragEvent<HTMLElement>) {
    if (!draggingRef.current) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }

  function handleContainerDrop(event: DragEvent<HTMLElement>) {
    const draggedId = draggingRef.current;
    if (!draggedId) return;
    event.preventDefault();
    droppedRef.current = true;
    if (!movedRef.current) return;
    movedRef.current = false;
    void persist(draggedId, orderRef.current);
  }

  return {
    /** Task IDs in their current visible order. */
    order,
    /** The task being dragged, or null. */
    draggingId,
    /** The task whose handle is held down, or null. */
    armedId,
    /** A save or service error worth showing to the student. */
    error,
    clearError: () => setError(null),
    containerProps: {
      onDragOver: handleContainerDragOver,
      onDrop: handleContainerDrop,
    } satisfies ContainerDragProps,
    itemProps: (id: string): ItemDragProps => {
      const reorderable = canReorder(id);
      return {
        draggable: reorderable && armedId === id,
        "data-reorder-id": id,
        onDragStart: (event) => {
          if (reorderable) handleDragStart(event, id);
        },
        onDragEnd: handleItemDragEnd,
        onDragOver: (event) => {
          if (reorderable) handleItemDragOver(event, id);
        },
      };
    },
    handleProps: (id: string): TaskDragHandleProps => ({
      onMouseDown: () => handleHandleMouseDown(id),
      onPointerDown: (event) => handleHandlePointerDown(event, id),
      onPointerMove: handleHandlePointerMove,
      onPointerUp: handleHandlePointerUp,
      onPointerCancel: handleHandlePointerCancel,
      onContextMenu: handleHandleContextMenu,
    }),
  };
}
