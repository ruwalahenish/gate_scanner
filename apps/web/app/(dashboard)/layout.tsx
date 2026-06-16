"use client";
import { Box } from "@mui/material";
import { useSelector, useDispatch } from "react-redux";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { NavigationProgress } from "@/components/layout/NavigationProgress";
import { toggleSidebar, setSidebarOpen } from "@/store/slices/uiSlice";
import { selectSidebarOpen } from "@/store/selectors";
import type { AppDispatch } from "@/store";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const dispatch     = useDispatch<AppDispatch>();
  const sidebarOpen  = useSelector(selectSidebarOpen);

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <NavigationProgress />
      <Sidebar
        mobileOpen={sidebarOpen}
        onMobileClose={() => dispatch(setSidebarOpen(false))}
      />
      <Box
        component="main"
        sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}
      >
        <TopBar onMenuClick={() => dispatch(toggleSidebar())} />
        <Box
          id="main-content"
          sx={{ flex: 1, overflow: "auto", p: { xs: 1.5, sm: 2, md: 3 } }}
        >
          {children}
        </Box>
      </Box>
    </Box>
  );
}
