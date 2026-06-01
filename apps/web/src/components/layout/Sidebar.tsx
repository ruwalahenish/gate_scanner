"use client";
import {
  Drawer, List, ListItemButton, ListItemIcon, ListItemText,
  Typography, Box, Chip, Divider,
} from "@mui/material";
import {
  Dashboard, ShowChart, AccountBalance, Star, Notifications,
  BarChart, Settings, TableChart,
} from "@mui/icons-material";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSelector } from "react-redux";
import type { RootState } from "@/store";

const DRAWER_WIDTH = 220;

const NAV = [
  { label: "Dashboard",  href: "/",            icon: <Dashboard /> },
  { label: "Portfolio",  href: "/portfolio",    icon: <AccountBalance /> },
  { label: "Watchlist",  href: "/watchlist",    icon: <Star /> },
  { label: "Alerts",     href: "/alerts",       icon: <Notifications /> },
  { label: "Analytics",  href: "/analytics",    icon: <BarChart /> },
  { label: "Backtest",   href: "/analytics/backtest", icon: <ShowChart /> },
  { label: "Stocks",     href: "/stocks",        icon: <TableChart /> },
  { label: "Settings",   href: "/settings",      icon: <Settings /> },
];

export function Sidebar() {
  const pathname = usePathname();
  const unreadAlerts = useSelector((s: RootState) => s.ws.unreadAlerts);
  const connected = useSelector((s: RootState) => s.ws.connected);

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        "& .MuiDrawer-paper": {
          width: DRAWER_WIDTH,
          bgcolor: "#12121a",
          borderRight: "1px solid rgba(255,255,255,0.06)",
          pt: 1,
        },
      }}
    >
      {/* Brand */}
      <Box sx={{ px: 2.5, py: 2 }}>
        <Typography variant="h6" fontWeight={700} color="primary" letterSpacing={-0.5}>
          GATE
        </Typography>
        <Box display="flex" alignItems="center" gap={0.5} mt={0.3}>
          <Box
            sx={{
              width: 7, height: 7, borderRadius: "50%",
              bgcolor: connected ? "success.main" : "error.main",
            }}
          />
          <Typography variant="caption" color="text.secondary">
            {connected ? "Live" : "Offline"}
          </Typography>
        </Box>
      </Box>

      <Divider sx={{ borderColor: "rgba(255,255,255,0.06)", mb: 1 }} />

      <List dense sx={{ px: 1 }}>
        {NAV.map((item) => {
          const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <ListItemButton
              key={item.href}
              component={Link}
              href={item.href}
              selected={active}
              sx={{
                borderRadius: 1.5,
                mb: 0.3,
                "&.Mui-selected": {
                  bgcolor: "rgba(99,102,241,0.15)",
                  "& .MuiListItemIcon-root": { color: "primary.main" },
                  "& .MuiListItemText-primary": { color: "primary.light", fontWeight: 600 },
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36, color: "text.secondary" }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{ variant: "body2" }}
              />
              {item.label === "Alerts" && unreadAlerts > 0 && (
                <Chip
                  label={unreadAlerts}
                  size="small"
                  color="warning"
                  sx={{ height: 18, fontSize: 10 }}
                />
              )}
            </ListItemButton>
          );
        })}
      </List>
    </Drawer>
  );
}
