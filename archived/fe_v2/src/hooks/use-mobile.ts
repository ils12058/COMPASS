import * as React from "react"

const MOBILE_BREAKPOINT = 768

function getIsMobile() {
  if (typeof window === "undefined") return false
  return window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`).matches
}

function subscribeToMobileChanges(onStoreChange: () => void) {
  const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
  mql.addEventListener("change", onStoreChange)
  return () => mql.removeEventListener("change", onStoreChange)
}

export function useIsMobile() {
  return React.useSyncExternalStore(
    subscribeToMobileChanges,
    getIsMobile,
    () => false,
  )
}
