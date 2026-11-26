"use client";

import { MotionConfig, MotionGlobalConfig } from "motion/react";
import { useEffect } from "react";

import { DUR, EASE } from "@/lib/motion";

/** ISSUES #10, Motion side: animations never start in a hidden tab (no frames there); they jump to their end state. */
function useSkipAnimationsWhileHidden() {
  useEffect(() => {
    const sync = () => {
      MotionGlobalConfig.skipAnimations = document.visibilityState === "hidden";
    };
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => document.removeEventListener("visibilitychange", sync);
  }, []);
}

/**
 * Motion settings for the signed-in app only. The animation library is not part of the public pages (landing,
 * sign-in), which keeps their first-load JavaScript smaller (ISSUES #57).
 */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  useSkipAnimationsWhileHidden();
  // reducedMotion="user": with the OS preference set, transform and layout animations are dropped, opacity stays.
  return (
    <MotionConfig reducedMotion="user" transition={{ duration: DUR.base, ease: EASE.out }}>
      {children}
    </MotionConfig>
  );
}
