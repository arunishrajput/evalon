"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export function AnimatedNumber({ value, className }: { value: number | string; className?: string }) {
  const [pulse, setPulse] = useState(false);
  const prev = useRef(value);

  useEffect(() => {
    if (prev.current !== value) {
      setPulse(true);
      prev.current = value;
      const timeout = setTimeout(() => setPulse(false), 400);
      return () => clearTimeout(timeout);
    }
  }, [value]);

  return (
    <span className={cn("inline-block transition-transform duration-300", pulse && "scale-125 text-accent", className)}>
      {value}
    </span>
  );
}
