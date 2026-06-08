"use client";
import { useEffect, useRef, useState, Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { Box, LinearProgress } from "@mui/material";

function ProgressInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const prevPath = useRef(pathname);
  const fallbackRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Stop the bar as soon as the new page has mounted (pathname updated)
  useEffect(() => {
    if (pathname !== prevPath.current) {
      setLoading(false);
      prevPath.current = pathname;
      if (fallbackRef.current) clearTimeout(fallbackRef.current);
    }
  }, [pathname, searchParams]);

  // Start the bar when the user clicks an internal link
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement).closest("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      try {
        const url = new URL(anchor.href, window.location.href);
        if (url.origin !== window.location.origin) return;
        if (url.pathname === pathname) return;
        setLoading(true);
        // Auto-dismiss after 10 s as a safety net
        fallbackRef.current = setTimeout(() => setLoading(false), 10_000);
      } catch {
        // malformed href — ignore
      }
    };

    document.addEventListener("click", handleClick, true);
    return () => {
      document.removeEventListener("click", handleClick, true);
      if (fallbackRef.current) clearTimeout(fallbackRef.current);
    };
  }, [pathname]);

  if (!loading) return null;

  return (
    <Box
      sx={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 9999,
        pointerEvents: "none",
      }}
    >
      <LinearProgress
        sx={{
          height: 2,
          bgcolor: "transparent",
          "& .MuiLinearProgress-bar": { bgcolor: "#6366f1" },
          "& .MuiLinearProgress-bar1Indeterminate": { bgcolor: "#6366f1" },
          "& .MuiLinearProgress-bar2Indeterminate": { bgcolor: "#818cf8" },
        }}
      />
    </Box>
  );
}

export function NavigationProgress() {
  return (
    <Suspense fallback={null}>
      <ProgressInner />
    </Suspense>
  );
}
