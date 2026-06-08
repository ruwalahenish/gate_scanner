import { Box } from "@mui/material";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { NavigationProgress } from "@/components/layout/NavigationProgress";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <NavigationProgress />
      <Sidebar />
      <Box
        component="main"
        sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}
      >
        <TopBar />
        <Box sx={{ flex: 1, overflow: "auto", p: 3 }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}
