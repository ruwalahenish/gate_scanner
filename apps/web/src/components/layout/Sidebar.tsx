"use client";
import {
  Drawer, List, ListItemButton, ListItemIcon, ListItemText,
  Typography, Box, Divider, Tooltip, useTheme, useMediaQuery,
} from "@mui/material";
import {
  Dashboard, TableChart, Scanner,
} from "@mui/icons-material";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSelector } from "react-redux";
import { selectWsConnected } from "@/store/selectors";

const DRAWER_WIDTH = 220;

const NAV_MAIN = [
  { label: "Dashboard",     href: "/",        icon: <Dashboard fontSize="small" /> },
  { label: "Master Stocks", href: "/stocks",   icon: <TableChart fontSize="small" /> },
  { label: "GATE Scanner",  href: "/scanner",  icon: <Scanner fontSize="small" /> },
];

const ITEM_SX = {
  borderRadius: 1.5,
  mb: 0.3,
  "&.Mui-selected": {
    bgcolor: "rgba(99,102,241,0.15)",
    "& .MuiListItemIcon-root": { color: "primary.main" },
    "& .MuiListItemText-primary": { color: "primary.light", fontWeight: 600 },
  },
} as const;

const SECTION_LABEL_SX = {
  px: 1.5,
  pt: 1.5,
  pb: 0.5,
  fontSize: "0.6rem",
  fontWeight: 700,
  letterSpacing: "0.1em",
  color: "text.disabled",
  textTransform: "uppercase" as const,
} as const;

interface SidebarProps {
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

function NavItem({ label, href, icon, pathname }: { label: string; href: string; icon: React.ReactNode; pathname: string }) {
  const active =
    href === "/"
      ? pathname === "/"
      : pathname === href || pathname.startsWith(href + "/");

  return (
    <ListItemButton
      key={href}
      component={Link}
      href={href}
      selected={active}
      aria-label={label}
      aria-current={active ? "page" : undefined}
      sx={ITEM_SX}
    >
      <ListItemIcon sx={{ minWidth: 34, color: "text.secondary" }}>
        {icon}
      </ListItemIcon>
      <ListItemText
        primary={label}
        primaryTypographyProps={{ variant: "body2" }}
      />
    </ListItemButton>
  );
}

function DrawerContent({ pathname, connected }: { pathname: string; connected: boolean }) {
  return (
    <>
      {/* Brand */}
      <Box role="banner" sx={{ px: 2.5, py: 2 }}>
        <Typography variant="h6" color="primary" letterSpacing={-0.5}>
          GATE
        </Typography>
        <Tooltip
          title={connected ? "WebSocket connected — live data active" : "WebSocket disconnected — retrying…"}
          placement="right"
        >
          <Box display="flex" alignItems="center" gap={0.5} mt={0.3} sx={{ cursor: "default", width: "fit-content" }}>
            <Box
              aria-label={connected ? "Connection status: live" : "Connection status: offline"}
              sx={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                bgcolor: connected ? "success.main" : "error.main",
                transition: "background-color 300ms ease",
              }}
            />
            <Typography variant="caption" color="text.secondary">
              {connected ? "Live" : "Offline"}
            </Typography>
          </Box>
        </Tooltip>
      </Box>

      <Divider sx={{ mb: 0.5 }} />

      <List dense sx={{ px: 1, flex: 1 }}>
        <Typography sx={SECTION_LABEL_SX}>Main</Typography>
        {NAV_MAIN.map((item) => (
          <NavItem key={item.href} {...item} pathname={pathname} />
        ))}
      </List>
    </>
  );
}

export function Sidebar({ mobileOpen = false, onMobileClose }: SidebarProps) {
  const pathname  = usePathname();
  const connected = useSelector(selectWsConnected);
  const theme     = useTheme();
  const isMobile  = useMediaQuery(theme.breakpoints.down("md"), { noSsr: true });

  const drawerSx = {
    width: DRAWER_WIDTH,
    flexShrink: 0,
    "& .MuiDrawer-paper": {
      width: DRAWER_WIDTH,
      bgcolor: "#12121a",
      borderRight: "1px solid rgba(255,255,255,0.06)",
      pt: 1,
      boxSizing: "border-box",
    },
  };

  return (
    <>
      {/* Skip-navigation link — visually hidden, visible on keyboard focus */}
      <Box
        component="a"
        href="#main-content"
        sx={{
          position: "fixed",
          top: -100,
          left: 8,
          zIndex: 9999,
          bgcolor: "primary.main",
          color: "white",
          px: 2,
          py: 1,
          borderRadius: 1,
          fontSize: "0.875rem",
          fontWeight: 600,
          textDecoration: "none",
          "&:focus": { top: 8 },
        }}
      >
        Skip to main content
      </Box>

      {/* Mobile: temporary overlay drawer */}
      {isMobile && (
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={onMobileClose}
          aria-label="Main navigation"
          ModalProps={{ keepMounted: true }}
          sx={drawerSx}
        >
          <DrawerContent pathname={pathname} connected={connected} />
        </Drawer>
      )}

      {/* Desktop: permanent sidebar */}
      {!isMobile && (
        <Drawer
          variant="permanent"
          open
          aria-label="Main navigation"
          sx={drawerSx}
        >
          <DrawerContent pathname={pathname} connected={connected} />
        </Drawer>
      )}
    </>
  );
}
