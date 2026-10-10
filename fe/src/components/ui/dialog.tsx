"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";

import { useDialogReturnFocus } from "@/components/ui/dialog-return-focus";
import { cn } from "@/lib/utils/cn";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export const DialogContent = forwardRef<
  ElementRef<typeof DialogPrimitive.Content>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    // False while the dialog has to stay open, such as while its own request is in flight. The
    // close button is removed, and Escape and outside clicks no longer close the dialog.
    dismissible?: boolean;
    closeLabel?: string;
    closeClassName?: string;
  }
>(
  (
    {
      children,
      className,
      dismissible = true,
      closeLabel = "Close dialog",
      closeClassName,
      onEscapeKeyDown,
      onInteractOutside,
      onOpenAutoFocus,
      onCloseAutoFocus,
      ...props
    },
    ref,
  ) => {
    const returnFocus = useDialogReturnFocus(onOpenAutoFocus, onCloseAutoFocus);

    return (
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-overlay" />
        <DialogPrimitive.Content
          ref={ref}
          {...props}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-md border border-border bg-surface-raised p-6 shadow-dialog focus:outline-none",
            className,
          )}
          onEscapeKeyDown={(event) => {
            onEscapeKeyDown?.(event);
            if (!dismissible) event.preventDefault();
          }}
          onInteractOutside={(event) => {
            onInteractOutside?.(event);
            if (!dismissible) event.preventDefault();
          }}
          onOpenAutoFocus={returnFocus.onOpenAutoFocus}
          onCloseAutoFocus={returnFocus.onCloseAutoFocus}
        >
          {children}
          {dismissible ? (
            <DialogPrimitive.Close
              className={cn(
                "absolute right-3 top-4 inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-muted hover:bg-surface-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                closeClassName,
              )}
              aria-label={closeLabel}
            >
              <X aria-hidden="true" size={18} />
            </DialogPrimitive.Close>
          ) : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    );
  },
);
DialogContent.displayName = "DialogContent";

// The right padding keeps a long title clear of the close button beside its first line.
export const DialogTitle = forwardRef<
  ElementRef<typeof DialogPrimitive.Title>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("pr-8 font-heading text-xl font-semibold text-ink", className)}
    {...props}
  />
));
DialogTitle.displayName = "DialogTitle";

export const DialogDescription = forwardRef<
  ElementRef<typeof DialogPrimitive.Description>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("mt-2 text-sm leading-6 text-muted", className)}
    {...props}
  />
));
DialogDescription.displayName = "DialogDescription";
