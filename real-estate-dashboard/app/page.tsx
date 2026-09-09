"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  LayoutDashboard,
  Users,
  Building2,
  MessageSquare,
  CircleDollarSign,
  HelpCircle,
  LogOut,
  Search,
  Bell,
  Plus,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Filter,
  PieChart as PieChartIcon,
  Clock,
  ChevronDown,
  User,
  SlidersHorizontal,
  ArrowUpDown,
  Bed,
  Bath,
  Maximize2,
  TrendingUp,
  Flame,
  Star,
  ChevronRight,
  CheckSquare,
  Square,
  MoreVertical,
  MapPin,
  X,
  Camera,
  ChevronLeft,
  Home,
  Building,
  UploadCloud,
  Trash2,
  Check,
  QrCode,
  Wifi,
  WifiOff,
  Loader2,
  Send,
  MapIcon,
} from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import LeadIntentCard from "@/src/components/LeadIntentCard";

// Interfaces
const formatNumber = (val?: number) =>
  val !== undefined ? val.toLocaleString("en-US") : "0";

// Helper to render dynamic trend pills
const renderTrendPill = (changeVal: number = 0) => {
  let bg = "bg-emerald-50 text-emerald-700";
  let symbol = "↑";

  if (changeVal < 0) {
    bg = "bg-rose-50 text-rose-600";
    symbol = "↓";
  } else if (changeVal === 0) {
    bg = "bg-slate-100 text-slate-600";
    symbol = "—";
  }

  return (
    <span
      className={`inline-flex items-center text-xs font-bold px-2 py-0.5 rounded-full ${bg}`}
    >
      {symbol}
      {Math.abs(changeVal)}%
    </span>
  );
};
// Add these at the top of your dashboard file
interface Lead {
  id: number;
  name: string;
  phone: string;
  intent: "BUYING" | "SELLING" | "RENT" | "AWAITING INFO";
  propertyType: string;
  budget: string;
  status: "NEW" | "FOLLOW UP" | "CLOSED";
  area?: string;
  location?: string;
  botEnabled?: boolean;
  addedTime: string;
}
const MAX_ACTIVITIES = 4;
interface Activity {
  id: number;
  type: "bot" | "user" | "action";
  text: string;
  highlightText: string;
  targetText?: string;
  time: string;
}

interface DashboardMetrics {
  total_leads: number;
  active_chats: number;
  property_matches: number;
  conversion_rate: number;
  total_leads_change?: number; // e.g. 12
  active_chats_change?: number; // e.g. 0
  property_matches_change?: number; // e.g. 5
  conversion_rate_change?: number; // e.g. -2
  buyers_count: number;
  sellers_count: number;
  hot_leads: Array<{
    id: number;
    name: string;
    phone_number: string;
    budget: string;
    intent: string;
    last_interaction: string;
  }>;
}

//properties
interface LeadInfo {
  name: string;
  initials: string;
  source: string;
  lastActive: string;
  budget: string;
  type: string;
  location: string;
  status: string;
}

interface PropertyInfo {
  title: string;
  price: string;
  tag?: string;
  image: string;
  beds: number;
  baths: number;
  sqft: number;
}
interface MatchPair {
  id: number;
  lead: LeadInfo;
  property: PropertyInfo;
  matchScore: number;
}
interface DemandedListing {
  id: number;
  title: string;
  price: string;
  image: string;
  tag?: "High Demand" | "Trending" | string;
  statText: string;
}

//Inventory Items
interface InventoryItem {
  id: number;
  title: string;
  location: string;
  price: string;
  status: "AVAILABLE" | "PENDING" | "SOLD";
  image: string;
  dateAdded: string;
  type: string;
}

export default function MalikPropertyDashboard() {
  const [mounted, setMounted] = useState(false);
  const [activeTab, setActiveTab] = useState<
    "Dashboard" | "Leads" | "Inventory" | "Property Matches"
  >("Dashboard");
  const [settingsSection, setSettingsSection] = useState<
    "Agency Profile" | "Account Details" | "Bot Configuration" | "Notifications"
  >("Agency Profile");

  // Settings State
  const [agencyName, setAgencyName] = useState("Malik Property");
  const [whatsappNumber, setWhatsappNumber] = useState("+1 (555) 123-4567");
  const [sendingProposalId, setSendingProposalId] = useState<string | null>(
    null,
  );
  const [businessAddress, setBusinessAddress] = useState(
    "123 Luxury Lane, Suite 400\nMetropolis, NY 10001",
  );

  const [autoReply, setAutoReply] = useState(true);
  const [leadQualification, setLeadQualification] = useState(true);
  const [smartMatching, setSmartMatching] = useState(false);

  const [whatsappAlerts, setWhatsappAlerts] = useState(true);
  const [newLeadEmails, setNewLeadEmails] = useState(true);
  const [dailyMatchSummaries, setDailyMatchSummaries] = useState(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  // Filter States for Leads View
  const [leadStatusFilter, setLeadStatusFilter] = useState("All Statuses");
  const [intentFilter, setIntentFilter] = useState("Buying & Selling");
  const [propertyTypeFilter, setPropertyTypeFilter] = useState("All Types");
  const [budgetRangeFilter, setBudgetRangeFilter] = useState("Any Budget");
  //QR
  const [status, setStatus] = useState("DISCONNECTED"); // "CONNECTED" | "NEEDS_QR" | "DISCONNECTED"
  const [qrCode, setQrCode] = useState(null);
  const [isConnectedWS, setIsConnectedWS] = useState(false);
  //properties
  const [sortOrder, setSortOrder] = useState<"highest" | "lowest">("highest");
  const [matchingPairs, setMatchingPairs] = useState<any[]>([]);
  const [matchPairs, setMatchPairs] = useState<MatchPair[]>([]);
  const [inventoryPage, setInventoryPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [activeDropdownId, setActiveDropdownId] = useState<number | null>(null);
  const ITEMS_PER_PAGE = 6;
  const [demandedListings, setDemandedListings] = useState<DemandedListing[]>(
    [],
  );
  const sortedPairs = [...matchingPairs].sort((a, b) => {
    if (sortOrder === "highest") {
      return b.matchScore - a.matchScore;
    } else {
      return a.matchScore - b.matchScore;
    }
  });

  const handleSendProposal = (match: any) => {
    try {
      setSendingProposalId(match.id);
      const phone = match.lead?.phone || match.lead?.phone_number || "";
      const cleanNumber = phone.replace(/\D/g, "");
      const formattedPhone = cleanNumber.startsWith("0")
        ? `92${cleanNumber.slice(1)}`
        : cleanNumber;

      const title = match.property?.title || "Property";
      const price = match.property?.price || "";
      const location = match.property?.location || "";
      const leadName = match.lead?.name || "there";

      const template =
        `Hello ${leadName},\n\n` +
        `Based on your preferences, here is a property match for you:\n\n` +
        `🏠 *${title}*\n` +
        `💰 Price: ${price}\n` +
        `${location ? `📍 Location: ${location}\n` : ""}\n` +
        `Let us know if you would like to schedule a viewing!`;

      const whatsappUrl = `https://wa.me/${formattedPhone}?text=${encodeURIComponent(template)}`;
      window.open(whatsappUrl, "_blank");
    } catch (error) {
      console.error("Error launching WhatsApp:", error);
    } finally {
      setSendingProposalId(null);
    }
  };

  const handleDeleteInventoryItem = async (itemId: number) => {
    // Optimistically remove from UI
    setInventory((prev) => prev.filter((item) => item.id !== itemId));
    setActiveDropdownId(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/inventory/${itemId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        fetchInventory(); // Revert/refresh if API fails
      }
    } catch (err) {
      console.error("Failed to delete inventory item:", err);
      fetchInventory();
    }
  };

  //bot
  const handleToggleBot = async (leadId: number, currentStatus: boolean) => {
    const nextStatus = !currentStatus;

    // Optimistic UI update
    setPipeLeads((prev) =>
      prev.map((l) => (l.id === leadId ? { ...l, botEnabled: nextStatus } : l)),
    );

    try {
      const res = await fetch(
        `${API_BASE_URL}/api/leads/${leadId}/toggle-bot`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: nextStatus }),
        },
      );

      if (!res.ok) fetchLeads(); // Revert on error
    } catch (err) {
      console.error("Failed to toggle bot:", err);
      fetchLeads();
    }
  };

  const handleOpenWhatsApp = (phone: string) => {
    const cleanNumber = phone.replace(/\D/g, "");
    const formattedPhone = cleanNumber.startsWith("0")
      ? `92${cleanNumber.slice(1)}`
      : cleanNumber;
    window.open(`https://wa.me/${formattedPhone}`, "_blank");
  };

  // Fetch initial real activities from SQLite backend
  const fetchBotActivities = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/dashboard/bot-activities`);
      if (res.ok) {
        const data: Activity[] = await res.json();
        setActivities(data);
      }
    } catch (err) {
      // Catch network drops smoothly without breaking UI state
      console.warn(
        "Backend API not reachable at http://localhost:8000. Retrying via WebSocket...",
      );
    }
  }, []);
  const [botStatus, setBotStatus] = useState<string>("DISCONNECTED");

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8000/ws/bot-status");

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "STATE_UPDATE") {
          setBotStatus(data.status);
          setQrCode(data.qr_code);
        }
      } catch (err) {
        console.error("WS message error:", err);
      }
    };

    return () => ws.close();
  }, []);

  const fetchPropertyMatches = async () => {
    setLoading(true);
    try {
      // Calls your new FastAPI backend matching endpoint
      const res = await fetch(`${API_BASE_URL}/api/property-matches`);
      if (res.ok) {
        const data = await res.json();
        setMatchingPairs(data);
      }

      // Calls inventory endpoint to populate "Highly Demanded Listings"
      const invRes = await fetch(`${API_BASE_URL}/api/inventory`);
      if (invRes.ok) {
        const invData = await invRes.json();
        const listingsArray = Array.isArray(invData)
          ? invData
          : invData.items || [];
        setDemandedListings(
          listingsArray.slice(0, 3).map((item: any, idx: number) => ({
            ...item,
            tag: idx === 0 ? "High Demand" : "Trending",
            statText: `${12 + idx * 4}% request surge this week`,
          })),
        );
      }
    } catch (err) {
      console.error("Failed to fetch property matches:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "Property Matches") {
      fetchPropertyMatches();
    }
  }, [activeTab]);

  //qr
  // useEffect(() => {
  //   let ws: WebSocket | null = null;
  //   let reconnectTimer: NodeJS.Timeout;

  //   const connect = () => {
  //     // FIX: Match exact host localhost:8000
  //     ws = new WebSocket(`${WS_BASE_URL}/ws/bot-status`);

  //     ws.onopen = () => {
  //       console.log("⚡ WebSocket connected to activity feed");
  //     };

  //     ws.onmessage = (event) => {
  //       try {
  //         const data = JSON.parse(event.data);
  //         if (data.type === "STATE_UPDATE") {
  //           setStatus(data.status);
  //           setQrCode(data.qr_code);
  //           if (data.activities) setActivities(data.activities);
  //         }
  //         if (data.type === "NEW_ACTIVITY") {
  //           setActivities((prev) => [data.activity, ...prev].slice(0, 20));
  //         }
  //       } catch (err) {
  //         console.error("Error parsing WS data:", err);
  //       }
  //     };

  //     ws.onclose = () => {
  //       // Reconnect after 3 seconds if disconnected
  //       reconnectTimer = setTimeout(connect, 3000);
  //     };

  //     ws.onerror = () => {
  //       // Keep console clean
  //     };
  //   };

  //   connect();

  //   return () => {
  //     clearTimeout(reconnectTimer);
  //     if (ws) ws.close();
  //   };
  // }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: NodeJS.Timeout;

    const connectWS = () => {
      ws = new WebSocket("ws://127.0.0.1:8000/ws/bot-status");

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "STATE_UPDATE") {
            setBotStatus(data.status);
            setQrCode(data.qr_code);
            if (Array.isArray(data.activities)) {
              setActivities(data.activities);
            }
          } else if (data.type === "NEW_ACTIVITY" && data.activity) {
            setActivities((prev) => {
              // Prevent duplicate insertion on the client side
              const exists = prev.some(
                (item) =>
                  item.id === data.activity.id ||
                  (item.text === data.activity.text &&
                    item.highlightText === data.activity.highlightText &&
                    item.targetText === data.activity.targetText),
              );
              if (exists) return prev;
              return [data.activity, ...prev].slice(0, 20);
            });
          }
        } catch (err) {
          console.error("Error parsing WS status payload:", err);
        }
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connectWS, 3000);
      };
    };

    connectWS();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  // useEffect(() => {
  //   const ws = new WebSocket("ws://127.0.0.1:8000/ws/bot-status");

  //   ws.onmessage = (event) => {
  //     // Ignore non-JSON frame checks (e.g., ping/pong frames)
  //     if (typeof event.data === "string" && !event.data.startsWith("{")) {
  //       return;
  //     }

  //     try {
  //       const message = JSON.parse(event.data);

  //       if (message.event === "NEW_LEAD") {
  //         fetchBotActivities();
  //       } else if (message.event === "BOT_MESSAGE") {
  //         const newActivity: Activity = {
  //           id: Date.now(),
  //           type: "bot",
  //           text: "Bot responded to inquiry from",
  //           highlightText: message.name || "Client",
  //           targetText: message.message_text
  //             ? `"${message.message_text}"`
  //             : "via WhatsApp",
  //           time: "JUST NOW",
  //         };

  //         // Prepend new activity and drop the oldest item beyond MAX_ACTIVITIES
  //         setActivities((prev) =>
  //           [newActivity, ...prev].slice(0, MAX_ACTIVITIES),
  //         );
  //       }
  //     } catch (e) {
  //       console.error("Error parsing WS payload:", e);
  //     }
  //   };

  //   return () => {
  //     if (
  //       ws.readyState === WebSocket.OPEN ||
  //       ws.readyState === WebSocket.CONNECTING
  //     ) {
  //       ws.close();
  //     }
  //   };
  // }, [fetchBotActivities]);

  useEffect(() => {
    fetchBotActivities();

    const ws = new WebSocket("ws://127.0.0.1:8000/ws/bot-status");

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "STATE_UPDATE" && Array.isArray(data.activities)) {
          setBotStatus(data.status);
          if (data.qr_code) setQrCode(data.qr_code);
          setActivities(data.activities);
        } else if (data.type === "NEW_ACTIVITY" && data.activity) {
          setActivities((prev) => {
            const isDup = prev.some(
              (item) =>
                item.id === data.activity.id ||
                (item.targetText === data.activity.targetText &&
                  item.text === data.activity.text),
            );
            if (isDup) return prev;
            return [data.activity, ...prev].slice(0, 20);
          });
        }
      } catch (err) {
        console.error("Error processing WebSocket activity event:", err);
      }
    };

    return () => {
      ws.close();
    };
  }, [fetchBotActivities]);

  const API_BASE_URL = "http://localhost:8000";
  const WS_BASE_URL = "ws://localhost:8000";
  //Inventory data
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("newest");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [visibleCount, setVisibleCount] = useState<number>(10);
  const [newProperty, setNewProperty] = useState({
    title: "",
    price: "",
    propertyType: "",
    address: "",
    city: "",
    district: "",
    beds: "0",
    baths: "0",
    sqft: "2500",
    price_per_marla: "",
    marlas: "",
  });

  const fetchInventory = async (page: number = inventoryPage) => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/inventory?page=${page}&limit=${ITEMS_PER_PAGE}`,
      );
      if (res.ok) {
        const data = await res.json();
        setInventory(data.items || []);
        setTotalPages(data.total_pages || 1); // Fixed key mapping from totalPages to total_pages matching backend
      }
    } catch (err) {
      console.warn("Could not connect to inventory API at 127.0.0.1:8000.");
    }
  };

  useEffect(() => {
    if (activeTab === "Inventory") {
      fetchInventory(inventoryPage);
    }

    // Real-time synchronization
    const host =
      typeof window !== "undefined"
        ? window.location.hostname || "127.0.0.1"
        : "127.0.0.1";
    const socket = new WebSocket(`ws://127.0.0.1:8000/ws/bot-status`);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (
          data.event === "INVENTORY_UPDATED" ||
          data.event === "NEW_PROPERTY"
        ) {
          fetchInventory();
        }
      } catch (err) {
        console.error("WS parse error:", err);
      }
    };

    return () => socket.close();
  }, [activeTab, inventoryPage]);

  const filteredInventory = useMemo(() => {
    return inventory
      .filter((item) => {
        const effectiveSearch = (searchTerm || searchQuery)
          .toLowerCase()
          .trim();
        const matchesSearch =
          !effectiveSearch ||
          item.title.toLowerCase().includes(effectiveSearch) ||
          item.location.toLowerCase().includes(effectiveSearch) ||
          item.type.toLowerCase().includes(effectiveSearch);
        const matchesStatus =
          statusFilter === "ALL" || item.status === statusFilter;
        const matchesType = typeFilter === "ALL" || item.type === typeFilter;
        return matchesSearch && matchesStatus && matchesType;
      })
      .sort((a, b) => {
        if (sortBy === "newest")
          return (
            new Date(b.dateAdded).getTime() - new Date(a.dateAdded).getTime()
          );
        if (sortBy === "oldest")
          return (
            new Date(a.dateAdded).getTime() - new Date(b.dateAdded).getTime()
          );
        return 0;
      });
  }, [inventory, searchTerm, statusFilter, typeFilter, sortBy]);

  const handleInventoryStatusChange = async (
    itemId: number,
    newStatus: string,
  ) => {
    setInventory((prev) =>
      prev.map((item) =>
        item.id === itemId ? { ...item, status: newStatus as any } : item,
      ),
    );

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/inventory/${itemId}/status`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        },
      );
      if (!response.ok) fetchInventory();
    } catch (error) {
      console.log("Failed to update inventory status:", error);
      fetchInventory();
    }
  };
  const handleStatusChange = async (leadId: number, newStatus: string) => {
    // Optimistic UI state update
    setPipeLeads((prevLeads) =>
      prevLeads.map((lead) =>
        lead.id === leadId ? { ...lead, status: newStatus as any } : lead,
      ),
    );

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/leads/${leadId}/status`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        },
      );

      if (!response.ok) {
        console.error("Failed to update lead status on backend");
        // Revert/refresh on failure
        fetchLeads();
      }
    } catch (err) {
      console.error("Network error while updating lead status:", err);
      fetchLeads();
    }
  };

  const handleFileSelect = (file: File) => {
    if (file && file.type.startsWith("image/")) {
      setSelectedFile(file);
      setImagePreview(URL.createObjectURL(file));
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };
  const handleSaveProperty = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const formattedLocation = `${newProperty.address}${newProperty.address ? ", " : ""}${newProperty.city}${newProperty.city && newProperty.district ? ", " : ""}${newProperty.district}`;

      const formData = new FormData();
      formData.append("title", newProperty.title);
      formData.append("type", newProperty.propertyType);
      formData.append("location", formattedLocation);
      formData.append("beds", newProperty.beds);
      formData.append("baths", newProperty.baths);
      formData.append("sqft", newProperty.sqft);
      formData.append("status", "AVAILABLE");

      // ✨ Append the new Marla fields here so the backend gets them!
      formData.append("price_per_marla", newProperty.price_per_marla || "0");
      formData.append("marlas", newProperty.marlas || "0");

      formData.append(
        "dateAdded",
        new Date().toLocaleDateString("en-US", {
          month: "short",
          day: "2-digit",
          year: "numeric",
        }),
      );

      if (selectedFile) {
        formData.append("file", selectedFile);
      }

      const response = await fetch(`${API_BASE_URL}/api/inventory`, {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        setIsAddModalOpen(false);
        setSelectedFile(null);
        setImagePreview(null);
        setNewProperty({
          title: "",
          price: "",
          propertyType: "",
          address: "",
          city: "",
          district: "",
          beds: "0",
          baths: "0",
          sqft: "2500",
          price_per_marla: "",
          marlas: "",
        });
        fetchInventory();
      }
    } catch (err) {
      console.error("Failed to add property with media:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Real-Time Database States
  const [metrics, setMetrics] = useState<DashboardMetrics>({
    total_leads: 0,
    active_chats: 0,
    property_matches: 0,
    conversion_rate: 0,
    buyers_count: 0,
    sellers_count: 0,
    hot_leads: [],
  });
  const [pipeLeads, setPipeLeads] = useState<Lead[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch real-time data from FastAPI backend
  const fetchDashboardMetrics = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/dashboard/overview");
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (error) {
      console.error("Failed to fetch dashboard metrics:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchLeads = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/leads");
      if (!res.ok) throw new Error("Failed to fetch leads");
      const data = await res.json();
      setPipeLeads(data);
    } catch (err) {
      console.error("Error loading leads:", err);
    } finally {
      setLoading(false);
    }
  };

  const filteredLeads = useMemo(() => {
    const query = (searchQuery || searchTerm).trim().toLowerCase();

    return pipeLeads.filter((lead) => {
      // Safely extract string fields
      const leadName = (lead.name || "").toString().toLowerCase();
      const leadPhone = (lead.phone || "").toString().toLowerCase();
      const leadIntent = (lead.intent || "").toString().toLowerCase();
      const leadPropType = (lead.propertyType || "").toString().toLowerCase();

      // 1. Search Query Check
      const matchesSearch =
        !query ||
        leadName.includes(query) ||
        leadPhone.includes(query) ||
        leadIntent.includes(query) ||
        leadPropType.includes(query);

      // 2. Status Filter Check
      const leadStatus = (lead.status || "").toString().toUpperCase();
      const matchesStatus =
        leadStatusFilter === "All Statuses" ||
        leadStatus === leadStatusFilter.toUpperCase();

      // 3. Intent Filter Check
      const rawIntent = (lead.intent || "").toString().trim().toUpperCase();
      const selectedIntent = intentFilter.trim().toUpperCase();
      const matchesIntent =
        intentFilter === "Buying & Selling" ||
        intentFilter === "All Intents" ||
        rawIntent === selectedIntent ||
        rawIntent.includes(selectedIntent);

      // 4. Property Type Check
      const matchesPropertyType =
        propertyTypeFilter === "All Types" ||
        leadPropType === propertyTypeFilter.toLowerCase();

      return (
        matchesSearch && matchesStatus && matchesIntent && matchesPropertyType
      );
    });
  }, [
    pipeLeads,
    searchQuery,
    searchTerm,
    leadStatusFilter,
    intentFilter,
    propertyTypeFilter,
  ]);
  const exportCSV = () => {
    if (pipelineLeads.length === 0) return;
    const headers = [
      "ID,Name,Phone,Intent,Property Type,Budget,Status,Added Time\n",
    ];
    const rows = pipelineLeads.map(
      (l) =>
        `${l.id},"${l.name}","${l.phone}","${l.intent}","${l.propertyType}","${l.budget}","${l.status}","${l.addedTime}"`,
    );
    const blob = new Blob([headers.concat(rows.join("\n")).join("")], {
      type: "text/csv",
    });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `leads_export_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  useEffect(() => {
    setVisibleCount(10);
  }, [leadStatusFilter, intentFilter, propertyTypeFilter]);
  useEffect(() => {
    if (activeTab === "Dashboard") {
      fetchDashboardMetrics();
    } else if (activeTab === "Leads") {
      fetchLeads();
    }
  }, [activeTab]);
  //leads
  useEffect(() => {
    fetchLeads();

    // WebSocket real-time updates
    const host =
      typeof window !== "undefined"
        ? window.location.hostname || "127.0.0.1"
        : "127.0.0.1";
    const socket = new WebSocket(`ws://127.0.0.1:8000/ws/bot-status`);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === "NEW_LEAD") {
          fetchLeads(); // Auto-refresh leads table when WhatsApp bot receives a new lead
        }
      } catch (err) {
        console.error("Error parsing WS event:", err);
      }
    };

    return () => socket.close();
  }, []);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;

    const connectWebSocket = () => {
      // Explicitly use 127.0.0.1 instead of localhost to prevent IPv6 lookup drops
      socket = new WebSocket("ws://127.0.0.1:8000/ws/bot-status");

      socket.onopen = () => {
        console.log("⚡ WebSocket connected to activity feed");
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "NEW_LEAD") {
            // Re-fetch dashboard metrics when a new lead hits the bot
            fetchDashboardMetrics();
          }
        } catch (err) {
          console.error("Error parsing WebSocket message:", err);
        }
      };

      socket.onerror = (error) => {
        console.warn("WebSocket temporary error, retrying...", error);
      };

      socket.onclose = (event) => {
        // Reconnect automatically if the server restarts or disconnects unexpectedly
        if (!event.wasClean) {
          reconnectTimeout = setTimeout(connectWebSocket, 3000);
        }
      };
    };

    connectWebSocket();

    // Clean cleanup to prevent React Strict Mode duplicates
    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (socket) {
        socket.onclose = null; // Prevent reconnect loop on intentional unmount
        socket.close();
      }
    };
  }, []);

  if (!mounted) return null;

  // Donut chart data for Lead Intent
  const totalIntentCount = metrics.buyers_count + metrics.sellers_count || 1;
  const buyerPercent = Math.round(
    (metrics.buyers_count / totalIntentCount) * 100,
  );
  const pieData = [
    { name: "BUYERS", value: metrics.buyers_count || 1, color: "#065f46" },
    { name: "SELLERS", value: metrics.sellers_count || 0, color: "#0f172a" },
  ];

  const recentActivities: Activity[] = [
    {
      id: 1,
      type: "bot",
      text: "Bot sent 3 property recommendations to",
      highlightText: "Sarah Jenkins",
      time: "2 MINUTES AGO",
    },
    {
      id: 2,
      type: "user",
      text: "Michael Chen initiated a new chat inquiring about",
      highlightText: "Downtown Lofts",
      time: "15 MINUTES AGO",
    },
    {
      id: 3,
      type: "action",
      text: "Bot scheduled a viewing for",
      highlightText: "David Ross",
      targetText: "at Villa Nova",
      time: "1 HOUR AGO",
    },
  ];

  const dashboardHotLeads = [
    {
      id: 1,
      name: "James Wilson",
      phone: "+923001234567",
      budget: "$850k - $1.2M",
      intent: "BUYING",
      lastInteraction: "Today, 10:42 AM",
      avatar:
        "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80",
    },
    {
      id: 2,
      name: "Elena Rodriguez",
      phone: "+923219876543",
      budget: "Pending Valuation",
      intent: "SELLING",
      lastInteraction: "Yesterday, 3:15 PM",
      avatar:
        "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=100&auto=format&fit=crop&q=80",
    },
    {
      id: 3,
      name: "Tom Baker",
      phone: "+923335557788",
      budget: "$400k - $600k",
      intent: "HOT LEAD",
      lastInteraction: "Oct 24, 9:00 AM",
      avatar:
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=80",
    },
  ];

  // Pipeline Leads Data
  const pipelineLeads: Lead[] = [
    {
      id: 2,
      name: "Michael Chen",
      phone: "+44 7700 900077",
      intent: "SELLING",
      propertyType: "Penthouse",
      budget: "TBD",
      status: "NEW",
      addedTime: "Added 5h ago",
    },
  ];
  console.log(
    "Current inventoryPage:",
    inventoryPage,
    "Total Pages:",
    totalPages,
  );
  return (
    <div
      className="flex h-screen bg-[#f8fafc] text-slate-800 font-sans overflow-hidden"
      suppressHydrationWarning
    >
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col justify-between p-5 z-10 flex-shrink-0">
        <div>
          <div className="flex items-center gap-3 mb-6 px-1">
            <div className="w-10 h-10 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-800 shadow-2xs">
              <span className="text-xs font-semibold tracking-wider">MP</span>
            </div>
            <div>
              <h1 className="font-bold text-slate-900 text-base leading-tight">
                Malik Property
              </h1>
              <p className="text-[11px] text-slate-500 font-medium">
                WhatsApp Lead Bot
              </p>
            </div>
          </div>

          <button className="w-full bg-black hover:bg-slate-800 text-white font-medium text-xs py-2.5 px-4 rounded-lg flex items-center justify-center gap-2 mb-6 transition-all shadow-2xs">
            <MapIcon className="w-4 h-4" />
            Dashboard Tabs
          </button>

          <nav className="space-y-1">
            {[
              { label: "Dashboard", icon: LayoutDashboard },
              { label: "Leads", icon: Users },
              { label: "Inventory", icon: Building },
              { label: "Property Matches", icon: Building2 },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.label;
              return (
                <button
                  key={item.label}
                  onClick={() => setActiveTab(item.label as any)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "text-slate-900 bg-slate-100 font-semibold"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 ${isActive ? "text-slate-900" : "text-slate-500"}`}
                  />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="pt-4 border-t border-slate-100 space-y-1">
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-50 font-medium">
            <HelpCircle className="w-4 h-4 text-slate-500" />
            Support
          </button>
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-50 font-medium">
            <LogOut className="w-4 h-4 text-slate-500" />
            Log Out
          </button>
        </div>
      </aside>

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between sticky top-0 z-20 flex-shrink-0">
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            {activeTab}
          </h2>

          <div className="flex items-center gap-4">
            <button className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-full transition-colors">
              <Bell className="w-4 h-4" />
            </button>
            <div className="w-8 h-8 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center text-slate-600 cursor-pointer">
              <User className="w-4 h-4" />
            </div>
          </div>
        </header>

        {/* Overview Dashboard View */}
        {activeTab === "Dashboard" && (
          <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
            <div className="flex justify-between items-end">
              <div>
                <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                  Overview Dashboard
                </h1>
                <p className="text-xs text-slate-500 mt-1">
                  Real-time metrics for your WhatsApp Bot
                </p>
              </div>
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 tracking-wider uppercase">
                <Clock className="w-3.5 h-3.5" />
                <span>Live Connection Active</span>
              </div>
            </div>

            {/* Metric Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Total Leads */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex justify-between items-start">
                  <h3 className="text-base font-extrabold text-slate-900 tracking-tight">
                    Total Leads
                  </h3>
                  <div className="p-2 bg-slate-100 rounded-lg">
                    <Users className="w-5 h-5 text-slate-900" />
                  </div>
                </div>
                <div className="mt-6 flex items-baseline gap-3">
                  <span className="text-4xl font-black text-slate-900 tracking-tight">
                    {loading ? "..." : formatNumber(metrics?.total_leads ?? 0)}
                  </span>
                  {!loading &&
                    renderTrendPill(metrics?.total_leads_change ?? 0)}
                </div>
              </div>

              {/* Active Chats */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex justify-between items-start">
                  <h3 className="text-base font-extrabold text-slate-900 tracking-tight">
                    Active Chats
                  </h3>
                  <div className="p-2 bg-indigo-50 rounded-lg">
                    <MessageSquare className="w-5 h-5 text-indigo-600" />
                  </div>
                </div>
                <div className="mt-6 flex items-baseline gap-3">
                  <span className="text-4xl font-black text-slate-900 tracking-tight">
                    {loading ? "..." : formatNumber(metrics?.active_chats ?? 0)}
                  </span>
                  {!loading &&
                    renderTrendPill(metrics?.active_chats_change ?? 0)}
                </div>
              </div>

              {/* Property Matches */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex justify-between items-start flex-1">
                  <h3 className="text-base font-extrabold text-slate-900 tracking-tight pr-2">
                    Property Matches
                  </h3>
                  <div className="p-2 bg-emerald-50 rounded-lg shrink-0">
                    <Building2 className="w-5 h-5 text-emerald-700" />
                  </div>
                </div>
                <div className="mt-6 flex items-baseline gap-3">
                  <span className="text-4xl font-black text-slate-900 tracking-tight">
                    {loading
                      ? "..."
                      : formatNumber(metrics?.property_matches ?? 0)}
                  </span>
                  {!loading &&
                    renderTrendPill(metrics?.property_matches_change ?? 0)}
                </div>
              </div>

              {/* Conversion Rate */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex justify-between items-start">
                  <h3 className="text-base font-extrabold text-slate-900 tracking-tight">
                    Conversion Rate
                  </h3>
                  <div className="p-2 bg-rose-50 rounded-lg">
                    <CircleDollarSign className="w-5 h-5 text-rose-500" />
                  </div>
                </div>
                <div className="mt-6 flex items-baseline gap-3">
                  <span className="text-4xl font-black text-slate-900 tracking-tight">
                    {loading ? "..." : `${metrics?.conversion_rate ?? 0}%`}
                  </span>
                  {!loading &&
                    renderTrendPill(metrics?.conversion_rate_change ?? 0)}
                </div>
              </div>
            </div>

            {/* Recent Activity & Intent */}
            <div className="grid grid-cols-3 gap-6">
              {/* Card constrained to fixed height with flex layout */}
              <div className="col-span-2 h-[380px] bg-white rounded-xl border border-slate-200 p-6 shadow-2xs flex flex-col justify-between">
                <div className="flex justify-between items-center mb-4 flex-shrink-0">
                  <h3 className="font-bold text-slate-900 text-base">
                    Recent Bot Activity
                  </h3>
                  <span className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-200/50 px-2 py-0.5 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Live Updates
                  </span>
                </div>
                {/* QR Code Scan Banner / Modal */}
                {botStatus === "NEEDS_QR" && qrCode && (
                  <div className="mb-6 p-6 bg-white border border-yellow-200 rounded-xl shadow-lg flex flex-col md:flex-row items-center justify-between gap-6">
                    <div>
                      <span className="px-3 py-1 bg-yellow-100 text-yellow-800 text-xs font-semibold rounded-full">
                        Action Required
                      </span>
                      <h3 className="text-xl font-bold mt-2 text-gray-900">
                        Scan QR Code to Connect Bot
                      </h3>
                      <p className="text-sm text-gray-600 mt-1">
                        Open WhatsApp on your phone &gt; Settings &gt; Linked
                        Devices &gt; Link a Device and scan this QR code.
                      </p>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg border">
                      <img
                        src={qrCode}
                        alt="WhatsApp QR Code"
                        className="w-48 h-48 object-contain"
                      />
                    </div>
                  </div>
                )}

                {/* Inner scroll container with strict scrollbar overflow */}
                <div className="flex-1 overflow-y-auto pr-1 space-y-2 scroll-smooth">
                  {activities.length === 0 ? (
                    <p className="text-xs font-semibold text-slate-400 py-12 text-center">
                      No recent bot activity recorded.
                    </p>
                  ) : (
                    activities.slice(0, 5).map((act, index) => (
                      <div
                        key={`${act.id || "act"}-${index}-${act.time}`}
                        className="flex gap-3 items-start text-xs border-b border-slate-100 pb-2.5 last:border-0 last:pb-0 animate-slideDown transition-all duration-300 ease-in-out"
                      >
                        <div className="w-2 h-2 rounded-full mt-1 bg-emerald-600 flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                          <p className="text-slate-800 leading-snug line-clamp-2">
                            {act.text}{" "}
                            <span className="font-bold text-slate-900">
                              {act.highlightText}
                            </span>{" "}
                            {act.targetText}
                          </p>
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-0.5 block">
                            {act.time}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <LeadIntentCard
                buyersCount={buyerPercent}
                sellersCount={100 - buyerPercent}
              />
            </div>

            {/* Hot Leads Table */}
            {(() => {
              // Fallback to pipeLeads if metrics.hot_leads is empty or undefined
              const allLeads =
                metrics?.hot_leads && metrics.hot_leads.length > 0
                  ? metrics.hot_leads
                  : (pipeLeads ?? []);

              const followUpLeads = allLeads.filter((lead: any) => {
                const combinedStr =
                  `${lead.status ?? ""} ${lead.intent ?? ""} ${lead.lead_status ?? ""}`.toLowerCase();
                return (
                  combinedStr.includes("follow") ||
                  combinedStr.includes("follow up") ||
                  combinedStr.includes("follow_up")
                );
              });

              return (
                <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
                  <div className="p-5 border-b border-slate-100 flex justify-between items-center">
                    <h3 className="font-bold text-slate-900 text-base">
                      Follow Up Leads ({followUpLeads.length})
                    </h3>
                  </div>

                  <table className="w-full text-left border-collapse text-xs">
                    <thead className="bg-slate-50 border-b border-slate-100 text-slate-400 font-semibold uppercase text-[10px]">
                      <tr>
                        <th className="py-3 px-6">Name / Phone</th>
                        <th className="py-3 px-6">Budget</th>
                        <th className="py-3 px-6">Intent / Status</th>
                        <th className="py-3 px-6">Last Interaction</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {followUpLeads.length > 0 ? (
                        followUpLeads.map((lead: any) => (
                          <tr
                            key={lead.id || lead.phone_number}
                            className="hover:bg-slate-50 transition-colors"
                          >
                            <td className="py-4 px-6 font-bold text-slate-900">
                              {lead.name && lead.name !== "Unknown"
                                ? lead.name
                                : lead.phone_number || "N/A"}
                            </td>
                            <td className="py-4 px-6 font-medium text-slate-700">
                              {lead.budget || "N/A"}
                            </td>
                            <td className="py-4 px-6">
                              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-50 text-amber-600 border border-amber-200">
                                {lead.status || lead.intent || "Follow Up"}
                              </span>
                            </td>
                            <td className="py-4 px-6 text-slate-500">
                              {lead.last_interaction || lead.addedTime || "N/A"}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td
                            colSpan={4}
                            className="py-8 text-center text-slate-400 font-medium"
                          >
                            No follow-up leads found
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              );
            })()}
          </main>
        )}

        {/* Leads Pipeline View */}
        {activeTab === "Leads" && (
          <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
            {/* Header */}
            <div className="flex justify-between items-start">
              <div>
                <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
                  Leads Pipeline
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                  Manage and qualify incoming inquiries from the WhatsApp bot in
                  real time.
                </p>
              </div>
              <button
                onClick={exportCSV}
                className="px-4 py-2.5 border border-slate-200 bg-white hover:bg-slate-50 text-slate-900 text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer"
              >
                Export CSV
              </button>
            </div>

            {/* Dynamic Filter Controls */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Status Filter */}
              <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <span className="text-[10px] font-extrabold text-slate-400 tracking-wider uppercase mb-1">
                  LEAD STATUS
                </span>
                <div className="relative flex items-center">
                  <select
                    value={leadStatusFilter}
                    onChange={(e) => setLeadStatusFilter(e.target.value)}
                    className="w-full text-xs font-extrabold text-slate-900 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 pr-8 focus:outline-none focus:ring-1 focus:ring-slate-400 appearance-none cursor-pointer transition-colors"
                  >
                    <option value="All Statuses">All Statuses</option>
                    <option value="NEW">New</option>
                    <option value="FOLLOW UP">Follow Up</option>
                    <option value="CLOSED">Closed</option>
                  </select>
                  <ChevronDown className="w-4 h-4 text-slate-400 absolute right-2.5 pointer-events-none" />
                </div>
              </div>

              {/* Intent Filter */}
              <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <span className="text-[10px] font-extrabold text-slate-400 tracking-wider uppercase mb-1">
                  INTENT
                </span>
                <div className="relative flex items-center">
                  <select
                    value={intentFilter}
                    onChange={(e) => setIntentFilter(e.target.value)}
                    className="w-full text-xs font-extrabold text-slate-900 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 pr-8 focus:outline-none focus:ring-1 focus:ring-slate-400 appearance-none cursor-pointer transition-colors"
                  >
                    <option value="Buying & Selling">
                      Buying & Selling (All)
                    </option>
                    <option value="BUYING">Buying Only</option>
                    <option value="SELLING">Selling Only</option>
                    <option value="RENT">Rent</option>
                    <option value="AWAITING INFO">Awaiting Info</option>
                  </select>
                  <ChevronDown className="w-4 h-4 text-slate-400 absolute right-2.5 pointer-events-none" />
                </div>
              </div>

              {/* Property Type Filter */}
              <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <span className="text-[10px] font-extrabold text-slate-400 tracking-wider uppercase mb-1">
                  PROPERTY TYPE
                </span>
                <div className="relative flex items-center">
                  <select
                    value={propertyTypeFilter}
                    onChange={(e) => setPropertyTypeFilter(e.target.value)}
                    className="w-full text-xs font-extrabold text-slate-900 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 pr-8 focus:outline-none focus:ring-1 focus:ring-slate-400 appearance-none cursor-pointer transition-colors"
                  >
                    <option value="All Types">All Types</option>
                    <option value="House">House / Villa</option>
                    <option value="Plot">Plot / Land</option>
                    <option value="Commercial">Commercial</option>
                  </select>
                  <ChevronDown className="w-4 h-4 text-slate-400 absolute right-2.5 pointer-events-none" />
                </div>
              </div>

              {/* Budget Filter */}
              <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <span className="text-[10px] font-extrabold text-slate-400 tracking-wider uppercase mb-1">
                  BUDGET RANGE
                </span>
                <div className="relative flex items-center">
                  <select className="w-full text-xs font-extrabold text-slate-900 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 pr-8 focus:outline-none focus:ring-1 focus:ring-slate-400 appearance-none cursor-pointer transition-colors">
                    <option value="Any Budget">Any Budget</option>
                  </select>
                  <ChevronDown className="w-4 h-4 text-slate-400 absolute right-2.5 pointer-events-none" />
                </div>
              </div>
            </div>

            {/* Leads List Table */}
            <div className="space-y-4 pt-2">
              {/* Search Bar */}
              <div className="relative w-full">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search leads by name, phone, or intent..."
                  value={searchTerm || searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setSearchTerm(e.target.value);
                  }}
                  className="w-full pl-9 pr-10 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-slate-900/10 text-slate-900 placeholder:text-slate-400"
                />
                {searchQuery && (
                  <button
                    onClick={() => {
                      setSearchQuery("");
                      setSearchTerm("");
                    }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
                  >
                    Clear
                  </button>
                )}
              </div>

              {/* Table Header (Standardized 12-column Grid) */}
              <div className="grid grid-cols-12 px-6 text-[11px] font-extrabold text-slate-400 uppercase tracking-wider">
                <div className="col-span-3">Contact</div>
                <div className="col-span-2">Intent & Type</div>
                <div className="col-span-2">Budget</div>
                <div className="col-span-2">Area/Location</div>
                <div className="col-span-2">Status</div>
                <div className="col-span-1 text-right">Actions</div>
              </div>

              {/* Loading state skeleton */}
              {loading ? (
                <div className="bg-white p-8 rounded-xl border border-slate-200 text-center font-medium text-slate-500">
                  Loading live leads...
                </div>
              ) : filteredLeads.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-2xl border border-slate-100">
                  <p className="text-sm font-medium text-slate-500">
                    No leads found matching "{searchQuery}"
                  </p>
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery("")}
                      className="mt-2 text-xs font-semibold text-slate-900 hover:underline"
                    >
                      Clear Search
                    </button>
                  )}
                </div>
              ) : (
                /* Real Dynamic Leads Row Mapping (Standardized 12-column Grid) */
                filteredLeads.slice(0, visibleCount).map((lead) => (
                  <div
                    key={lead.id}
                    className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs hover:border-slate-300 transition-all grid grid-cols-12 items-center"
                  >
                    {/* Contact Column (col-span-3) */}
                    <div className="col-span-3 flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 shrink-0">
                        <User className="w-5 h-5 text-slate-500" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-extrabold text-slate-900 text-sm leading-tight truncate">
                          {lead.name}
                        </h4>
                        <p className="text-xs font-semibold text-slate-500 mt-0.5 truncate">
                          {lead.phone}
                        </p>
                      </div>
                    </div>

                    {/* Intent & Type Column (col-span-2) */}
                    <div className="col-span-2">
                      <span
                        className={`inline-block pr-1 py-0.5 rounded text-[9px] font-black tracking-wide uppercase mb-1 ${
                          lead.intent.includes("SELL")
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-slate-100 text-slate-800"
                        }`}
                      >
                        {lead.intent}
                      </span>
                      <p className="text-xs text-slate-900 font-bold truncate">
                        {lead.propertyType}
                      </p>
                    </div>

                    {/* Budget Column (col-span-2) */}
                    <div className="col-span-2">
                      <p className="text-xs font-black text-slate-900 truncate">
                        {lead.budget}
                      </p>
                    </div>

                    {/* Area/Location Column (col-span-2) */}
                    <div className="col-span-2">
                      <p className="text-xs font-black text-slate-900 truncate">
                        {lead.area && lead.area.trim() !== ""
                          ? lead.area
                          : "Not Specified"}
                      </p>
                      <p className="text-xs font-medium text-slate-500 truncate">
                        {lead.location && lead.location.trim() !== ""
                          ? lead.location
                          : "Not Specified"}
                      </p>
                    </div>

                    {/* Status Column (col-span-2) */}
                    <div className="col-span-2">
                      <div className="relative inline-block">
                        <select
                          value={lead.status}
                          onChange={(e) =>
                            handleStatusChange(lead.id, e.target.value)
                          }
                          className={`px-2 py-1 rounded text-[10px] font-black tracking-wider uppercase border appearance-none pr-6 cursor-pointer focus:outline-none transition-colors ${
                            lead.status === "NEW"
                              ? "bg-blue-100 text-blue-700 border-blue-300"
                              : lead.status === "FOLLOW UP"
                                ? "bg-amber-100 text-amber-700 border-amber-300"
                                : "bg-slate-100 text-slate-600 border-slate-300"
                          }`}
                        >
                          <option value="NEW">NEW</option>
                          <option value="FOLLOW UP">FOLLOW UP</option>
                          <option value="CLOSED">CLOSED</option>
                        </select>
                        <ChevronDown className="w-3 h-3 text-slate-500 absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                      </div>
                      <p className="text-[10px] font-semibold text-slate-400 mt-1">
                        {lead.addedTime}
                      </p>
                    </div>

                    {/* Actions Column (col-span-1) */}
                    <div className="col-span-1 flex items-center justify-end gap-1.5">
                      {/* WhatsApp Direct Action */}
                      <button
                        onClick={() => handleOpenWhatsApp(lead.phone)}
                        title="Open WhatsApp Chat"
                        className="p-2 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 transition-colors"
                      >
                        <MessageSquare className="w-4 h-4" />
                      </button>

                      {/* Start / Stop Bot Action */}
                      <button
                        onClick={() =>
                          handleToggleBot(lead.id, lead.botEnabled ?? true)
                        }
                        title={
                          (lead.botEnabled ?? true) ? "Pause Bot" : "Start Bot"
                        }
                        className={`p-2 rounded-lg transition-colors ${
                          (lead.botEnabled ?? true)
                            ? "bg-slate-100 hover:bg-rose-50 text-slate-700 hover:text-rose-600"
                            : "bg-amber-100 hover:bg-emerald-50 text-amber-800 hover:text-emerald-700"
                        }`}
                      >
                        {(lead.botEnabled ?? true) ? (
                          <Wifi className="w-4 h-4" />
                        ) : (
                          <WifiOff className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                ))
              )}

              {/* Footer Load Control */}
              {!loading && filteredLeads.length > visibleCount && (
                <div className="pt-6 text-center">
                  <button
                    onClick={() => setVisibleCount((prev) => prev + 10)}
                    className="text-xs font-bold text-slate-600 hover:text-slate-900 inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    Load More Leads ({filteredLeads.length - visibleCount}{" "}
                    remaining) <ChevronDown className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          </main>
        )}

        {/* Intelligence Matches Screen */}
        {activeTab === "Property Matches" && (
          <main className="p-8 space-y-8 max-w-7xl mx-auto w-full">
            {/* Header & Controls */}
            <div className="flex justify-between items-start">
              <div>
                <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
                  Intelligence Matches
                </h1>
                <p className="text-xs font-semibold text-slate-500 mt-1">
                  Bot-curated property recommendations based on active lead
                  conversations.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() =>
                    setSortOrder(sortOrder === "highest" ? "lowest" : "highest")
                  }
                  className="px-3.5 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-xl flex items-center gap-2 shadow-xs transition-colors cursor-pointer"
                >
                  <ArrowUpDown className="w-3.5 h-3.5" />
                  Sort:{" "}
                  {sortOrder === "highest" ? "Highest Score" : "Lowest Score"}
                </button>
              </div>
            </div>

            {/* Highly Demanded Listings Quick Row */}
            {demandedListings.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-400">
                  Trending Inventory Surges
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {demandedListings.map((item) => (
                    <div
                      key={item.id}
                      className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center gap-4"
                    >
                      <img
                        src={item.image}
                        alt={item.title}
                        className="w-16 h-16 rounded-lg object-cover shrink-0"
                      />
                      <div className="min-w-0 flex-1">
                        <span className="inline-block px-2 py-0.5 rounded text-[9px] font-black tracking-wider uppercase bg-emerald-50 text-emerald-700 mb-1">
                          {item.tag}
                        </span>
                        <h4 className="font-extrabold text-slate-900 text-xs truncate">
                          {item.title}
                        </h4>
                        <p className="text-[11px] font-semibold text-slate-500 mt-0.5">
                          {item.statText}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Matching Pairs List */}
            <div className="space-y-4">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-400">
                AI Lead-to-Property Match Pairs ({sortedPairs.length})
              </h3>

              {loading ? (
                <div className="bg-white p-12 rounded-xl border border-slate-200 text-center text-slate-500 font-medium">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-slate-900" />
                  Curating smart property matches...
                </div>
              ) : sortedPairs.length === 0 ? (
                <div className="bg-white p-12 rounded-xl border border-slate-200 text-center text-slate-500 font-medium">
                  No high-confidence property matches found at the moment. Keep
                  chatting with leads!
                </div>
              ) : (
                sortedPairs.map((match) => (
                  <div
                    key={match.id}
                    className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs hover:border-slate-300 transition-all grid grid-cols-1 lg:grid-cols-12 gap-6 items-center"
                  >
                    {/* Lead Info (col-span-4) */}
                    <div className="lg:col-span-4 space-y-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-slate-900 text-white font-extrabold flex items-center justify-center text-xs tracking-wider shrink-0">
                          {match.lead.initials}
                        </div>
                        <div className="min-w-0">
                          <h4 className="font-extrabold text-slate-900 text-sm truncate">
                            {match.lead.name}
                          </h4>
                          <p className="text-xs font-semibold text-slate-500 truncate">
                            {match.lead.phone} • {match.lead.source}
                          </p>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs bg-slate-50 p-3 rounded-xl border border-slate-100">
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 block uppercase">
                            Intent
                          </span>
                          <span className="font-extrabold text-slate-900">
                            {match.lead.intent}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 block uppercase">
                            Budget
                          </span>
                          <span className="font-extrabold text-slate-900 truncate block">
                            {match.lead.budget}
                          </span>
                        </div>
                        <div className="col-span-2 pt-1 border-t border-slate-200/60 mt-1">
                          <span className="text-[10px] font-bold text-slate-400 block uppercase">
                            Target Type & Location
                          </span>
                          <span className="font-semibold text-slate-700">
                            {match.lead.type} in {match.lead.location}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Match Score Badge (col-span-2 text-center) */}
                    <div className="lg:col-span-2 flex flex-col items-center justify-center py-3 bg-emerald-50/50 border border-emerald-100 rounded-xl">
                      <Flame className="w-5 h-5 text-emerald-600 mb-1" />
                      <span className="text-2xl font-black text-emerald-700 tracking-tight">
                        {match.matchScore}%
                      </span>
                      <span className="text-[10px] font-extrabold text-emerald-800 uppercase tracking-wider">
                        Confidence
                      </span>
                    </div>

                    {/* Matched Property Card (col-span-6) */}
                    <div className="lg:col-span-6 flex flex-col sm:flex-row items-center gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200/80">
                      <img
                        src={match.property.image}
                        alt={match.property.title}
                        className="w-full sm:w-28 h-28 rounded-lg object-cover shrink-0"
                      />
                      <div className="flex-1 min-w-0 w-full space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="px-2 py-0.5 rounded text-[9px] font-black tracking-wider uppercase bg-slate-200 text-slate-800">
                            {match.property.tag}
                          </span>
                          <span className="text-xs font-black text-slate-900">
                            {match.property.price}
                          </span>
                        </div>
                        <h4 className="font-extrabold text-slate-900 text-sm truncate">
                          {match.property.title}
                        </h4>
                        <div className="flex items-center gap-3 text-xs text-slate-500 font-semibold pt-1">
                          {match.property.beds > 0 && (
                            <span className="flex items-center gap-1">
                              <Bed className="w-3.5 h-3.5" />{" "}
                              {match.property.beds} Beds
                            </span>
                          )}
                          {match.property.baths > 0 && (
                            <span className="flex items-center gap-1">
                              <Bath className="w-3.5 h-3.5" />{" "}
                              {match.property.baths} Baths
                            </span>
                          )}
                          {match.property.sqft > 0 && (
                            <span className="flex items-center gap-1">
                              <Maximize2 className="w-3.5 h-3.5" />{" "}
                              {match.property.sqft} sqft
                            </span>
                          )}
                        </div>

                        <div className="pt-2 flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleSendProposal(match)}
                            disabled={sendingProposalId === match.id}
                            className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition-all shadow-xs cursor-pointer disabled:opacity-50"
                          >
                            {sendingProposalId === match.id ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                Dispatching...
                              </>
                            ) : (
                              <>
                                <Send className="w-3.5 h-3.5" />
                                Send WhatsApp Proposal
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </main>
        )}

        {/* Inventory */}
        {activeTab === "Inventory" && (
          <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
            {/* Page Header */}
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-black text-slate-900 tracking-tight">
                  Inventory Management
                </h1>
                <p className="text-xs font-semibold text-slate-500 mt-1">
                  Manage your active, pending, and sold property listings.
                </p>
              </div>

              <button
                onClick={() => setIsAddModalOpen(true)}
                className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl flex items-center gap-2 shadow-sm transition-colors cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                Add New Property
              </button>
            </div>

            {/* Search & Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-3 rounded-2xl border border-slate-200 shadow-xs">
              <div className="flex items-center gap-3 flex-1 min-w-[280px]">
                <div className="relative w-full">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search by address, MLS, or client..."
                    value={searchTerm}
                    onChange={(e) => {
                      setSearchTerm(e.target.value);
                      setSearchQuery(e.target.value);
                    }}
                    className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-slate-900/10"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3 flex-wrap">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 focus:outline-none"
                >
                  <option value="ALL">All Status</option>
                  <option value="AVAILABLE">Available</option>
                  <option value="PENDING">Pending</option>
                  <option value="SOLD">Sold</option>
                </select>

                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 focus:outline-none"
                >
                  <option value="ALL">Property Type</option>
                  <option value="Villa">Villa</option>
                  <option value="Apartment">Apartment</option>
                  <option value="Commercial">Commercial</option>
                  <option value="House">House</option>
                </select>

                <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
                  <span className="text-xs font-bold text-slate-400">
                    Sort by:
                  </span>
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 focus:outline-none"
                  >
                    <option value="newest">Newest Added</option>
                    <option value="oldest">Oldest Added</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Listings Grid */}
            {loading ? (
              <div className="bg-white p-12 rounded-2xl border border-slate-200 text-center text-slate-400 font-bold text-sm">
                Syncing inventory database...
              </div>
            ) : filteredInventory.length === 0 ? (
              <div className="bg-white p-12 rounded-2xl border border-slate-200 text-center text-slate-500 font-semibold text-sm">
                No properties found matching your search.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredInventory.map((item) => (
                  <div
                    key={item.id}
                    className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs group hover:shadow-md transition-all duration-200"
                  >
                    <div className="relative h-48 overflow-hidden">
                      <img
                        src={item.image}
                        alt={item.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      <div className="absolute top-3 left-3 z-10">
                        <select
                          value={item.status}
                          onChange={(e) =>
                            handleInventoryStatusChange(item.id, e.target.value)
                          }
                          className={`px-2.5 py-1 text-[10px] font-black rounded-md tracking-wider uppercase border appearance-none cursor-pointer focus:outline-none transition-colors ${
                            item.status === "AVAILABLE"
                              ? "bg-emerald-500/90 text-white border-emerald-600"
                              : item.status === "PENDING"
                                ? "bg-amber-500/90 text-white border-amber-600"
                                : "bg-rose-500/90 text-white border-rose-600"
                          }`}
                        >
                          <option
                            value="AVAILABLE"
                            className="bg-white text-slate-900"
                          >
                            AVAILABLE
                          </option>
                          <option
                            value="PENDING"
                            className="bg-white text-slate-900"
                          >
                            PENDING
                          </option>
                          <option
                            value="SOLD"
                            className="bg-white text-slate-900"
                          >
                            SOLD
                          </option>
                        </select>
                      </div>
                    </div>

                    <div className="p-5">
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="font-extrabold text-slate-900 text-base leading-snug">
                            {item.title}
                          </h3>
                          <p className="text-xs font-medium text-slate-400 mt-1 flex items-center gap-1">
                            <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                            {item.location}
                          </p>
                        </div>
                        <div className="relative">
                          <button
                            onClick={() =>
                              setActiveDropdownId(
                                activeDropdownId === item.id ? null : item.id,
                              )
                            }
                            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>

                          {activeDropdownId === item.id && (
                            <div className="absolute right-0 mt-1 w-36 bg-white border border-slate-200 rounded-lg shadow-lg py-1 z-30">
                              <button
                                onClick={() =>
                                  handleDeleteInventoryItem(item.id)
                                }
                                className="w-full text-left px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 flex items-center gap-2"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                Delete Property
                              </button>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="mt-6 pt-4 border-t border-slate-100 flex justify-between items-end">
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                            {item.status === "SOLD"
                              ? "Sold Price"
                              : item.status === "PENDING"
                                ? "Contract Price"
                                : "Asking Price"}
                          </span>
                          <span className="text-lg font-black text-slate-900">
                            {item.price}
                          </span>
                        </div>

                        <div className="text-right">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                            {item.status === "SOLD" ? "Closed" : "Added"}
                          </span>
                          <span className="text-xs font-extrabold text-slate-700">
                            {item.dateAdded}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination Bar */}
            {totalPages > 0 && (
              <div className="flex items-center justify-between bg-white px-6 py-4 rounded-2xl border border-slate-200 mt-6 shadow-xs">
                <p className="text-xs font-semibold text-slate-500">
                  Showing page{" "}
                  <span className="font-bold text-slate-800">
                    {inventoryPage}
                  </span>{" "}
                  of{" "}
                  <span className="font-bold text-slate-800">{totalPages}</span>
                </p>

                <div className="flex items-center gap-2">
                  {/* Previous Button */}
                  <button
                    onClick={() =>
                      setInventoryPage((prev) => Math.max(prev - 1, 1))
                    }
                    disabled={inventoryPage === 1}
                    className="p-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>

                  {/* Dynamic Page Tab Numbers */}
                  {Array.from({ length: totalPages }, (_, index) => {
                    const pageNumber = index + 1;
                    const isActive = pageNumber === inventoryPage;
                    return (
                      <button
                        key={pageNumber}
                        onClick={() => setInventoryPage(pageNumber)}
                        className={`w-8 h-8 rounded-xl text-xs font-black transition-all ${
                          isActive
                            ? "bg-slate-900 text-white shadow-xs scale-105"
                            : "bg-slate-50 text-slate-700 hover:bg-slate-100 border border-slate-200"
                        }`}
                      >
                        {pageNumber}
                      </button>
                    );
                  })}

                  {/* Next Button */}
                  <button
                    onClick={() =>
                      setInventoryPage((prev) => Math.min(prev + 1, totalPages))
                    }
                    disabled={inventoryPage === totalPages}
                    className="p-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
            {/* Add New Property Modal */}
            {isAddModalOpen && (
              <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-2xl max-w-xl w-full shadow-2xl overflow-hidden border border-slate-100 animate-in fade-in zoom-in-95 duration-150">
                  {/* Header */}
                  <div className="flex justify-between items-center px-6 py-5 border-b border-slate-100">
                    <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                      Add New Property
                    </h2>
                    <button
                      type="button"
                      onClick={() => setIsAddModalOpen(false)}
                      className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>

                  <form onSubmit={handleSaveProperty}>
                    <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
                      {/* Section 1: Basic Information */}
                      <div className="space-y-4">
                        <div className="border-b border-slate-200 pb-1">
                          <h3 className="text-sm font-semibold text-slate-900">
                            Basic Information
                          </h3>
                        </div>

                        <div>
                          <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                            Property Title
                          </label>
                          <input
                            type="text"
                            required
                            placeholder="e.g. Modern Villa with Pool"
                            value={newProperty.title}
                            onChange={(e) =>
                              setNewProperty({
                                ...newProperty,
                                title: e.target.value,
                              })
                            }
                            className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 placeholder-slate-400 focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                          />
                        </div>

                        {/* Marla & Price breakdown */}
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                              Price / Marla (PKR)
                            </label>
                            <input
                              type="number"
                              required
                              step="any"
                              placeholder="e.g. 500000"
                              value={newProperty.price_per_marla || ""}
                              onChange={(e) =>
                                setNewProperty({
                                  ...newProperty,
                                  price_per_marla: e.target.value,
                                })
                              }
                              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 placeholder-slate-400 focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                            />
                          </div>

                          <div>
                            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                              Total Marlas
                            </label>
                            <input
                              type="number"
                              required
                              step="any"
                              placeholder="e.g. 5, 10, 20"
                              value={newProperty.marlas || ""}
                              onChange={(e) =>
                                setNewProperty({
                                  ...newProperty,
                                  marlas: e.target.value,
                                })
                              }
                              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 placeholder-slate-400 focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                            />
                          </div>
                        </div>

                        {/* Auto calculated total price display banner */}
                        {newProperty.price_per_marla && newProperty.marlas && (
                          <div className="p-3 bg-slate-100 rounded-lg flex justify-between items-center text-xs">
                            <span className="font-medium text-slate-600">
                              Calculated Total Price:
                            </span>
                            <span className="font-bold text-slate-900">
                              PKR{" "}
                              {(
                                Number(newProperty.price_per_marla) *
                                Number(newProperty.marlas)
                              ).toLocaleString()}
                            </span>
                          </div>
                        )}

                        <div>
                          <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                            Property Type
                          </label>
                          <div className="relative">
                            <select
                              required
                              value={newProperty.propertyType}
                              onChange={(e) =>
                                setNewProperty({
                                  ...newProperty,
                                  propertyType: e.target.value,
                                })
                              }
                              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 bg-white appearance-none focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                            >
                              <option value="" disabled>
                                Select type
                              </option>
                              <option value="Villa">Villa</option>
                              <option value="Apartment">Apartment</option>
                              <option value="Commercial">Commercial</option>
                              <option value="House">House</option>
                              <option value="Plot">Plot</option>
                            </select>
                            <ChevronDown className="w-4 h-4 text-slate-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                          </div>
                        </div>
                      </div>

                      {/* Section 2: Location */}
                      <div className="space-y-4">
                        <div className="border-b border-slate-200 pb-1">
                          <h3 className="text-sm font-semibold text-slate-900">
                            Location
                          </h3>
                        </div>

                        <div>
                          <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                            Address
                          </label>
                          <input
                            type="text"
                            required
                            placeholder="Street Address"
                            value={newProperty.address}
                            onChange={(e) =>
                              setNewProperty({
                                ...newProperty,
                                address: e.target.value,
                              })
                            }
                            className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 placeholder-slate-400 focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                              City
                            </label>
                            <input
                              type="text"
                              required
                              placeholder="City Name"
                              value={newProperty.city}
                              onChange={(e) =>
                                setNewProperty({
                                  ...newProperty,
                                  city: e.target.value,
                                })
                              }
                              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 placeholder-slate-400 focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                            />
                          </div>

                          <div>
                            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                              District
                            </label>
                            <input
                              type="text"
                              required
                              placeholder="District"
                              value={newProperty.district}
                              onChange={(e) =>
                                setNewProperty({
                                  ...newProperty,
                                  district: e.target.value,
                                })
                              }
                              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 placeholder-slate-400 focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                            />
                          </div>
                        </div>
                      </div>

                      {/* Section 3: Specifications */}
                      <div className="space-y-4">
                        <div className="border-b border-slate-200 pb-1">
                          <h3 className="text-sm font-semibold text-slate-900">
                            Specifications
                          </h3>
                        </div>

                        <div className="grid grid-cols-3 gap-4">
                          <div>
                            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                              Beds
                            </label>
                            <input
                              type="number"
                              min="0"
                              value={newProperty.beds}
                              onChange={(e) =>
                                setNewProperty({
                                  ...newProperty,
                                  beds: e.target.value,
                                })
                              }
                              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                            />
                          </div>

                          <div>
                            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                              Baths
                            </label>
                            <input
                              type="number"
                              min="0"
                              value={newProperty.baths}
                              onChange={(e) =>
                                setNewProperty({
                                  ...newProperty,
                                  baths: e.target.value,
                                })
                              }
                              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                            />
                          </div>

                          <div>
                            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">
                              Sq Ft
                            </label>
                            <input
                              type="number"
                              min="0"
                              value={newProperty.sqft}
                              onChange={(e) =>
                                setNewProperty({
                                  ...newProperty,
                                  sqft: e.target.value,
                                })
                              }
                              className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-normal text-slate-800 focus:outline-none focus:border-slate-800 focus:ring-1 focus:ring-slate-800"
                            />
                          </div>
                        </div>
                      </div>

                      {/* Section 4: Media */}
                      <div className="space-y-4">
                        <div className="border-b border-slate-200 pb-1">
                          <h3 className="text-sm font-semibold text-slate-900">
                            Media
                          </h3>
                        </div>

                        {!imagePreview ? (
                          <div
                            onDragOver={(e) => {
                              e.preventDefault();
                              setIsDragging(true);
                            }}
                            onDragLeave={() => setIsDragging(false)}
                            onDrop={handleDrop}
                            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors flex flex-col items-center justify-center ${
                              isDragging
                                ? "border-slate-800 bg-slate-100/70"
                                : "border-slate-300/80 bg-slate-100/40 hover:bg-slate-100/70"
                            }`}
                          >
                            <div className="w-12 h-12 rounded-xl bg-slate-200/60 flex items-center justify-center mb-3 text-slate-800">
                              <UploadCloud className="w-6 h-6 stroke-[1.75]" />
                            </div>

                            <h4 className="text-sm font-bold text-slate-900">
                              Drag & drop images here
                            </h4>
                            <p className="text-xs text-slate-500 font-normal mt-0.5 mb-4">
                              or click to browse from your computer
                            </p>

                            <label className="cursor-pointer inline-flex items-center justify-center px-4 py-2 border border-slate-300 bg-white hover:bg-slate-50 text-slate-800 text-xs font-semibold rounded-lg shadow-2xs transition-colors">
                              Select Files
                              <input
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => {
                                  if (e.target.files && e.target.files[0]) {
                                    handleFileSelect(e.target.files[0]);
                                  }
                                }}
                              />
                            </label>
                          </div>
                        ) : (
                          <div className="relative rounded-xl overflow-hidden border border-slate-200 group">
                            <img
                              src={imagePreview}
                              alt="Property preview"
                              className="w-full h-44 object-cover"
                            />
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedFile(null);
                                setImagePreview(null);
                              }}
                              className="absolute top-3 right-3 p-2 bg-slate-900/80 text-white rounded-lg hover:bg-rose-600 transition-colors shadow-xs"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Footer Actions */}
                    <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-100 bg-slate-50/50">
                      <button
                        type="button"
                        onClick={() => setIsAddModalOpen(false)}
                        className="px-5 py-2.5 text-xs font-semibold text-slate-700 hover:text-slate-900 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={isSubmitting}
                        className="px-5 py-2.5 bg-black hover:bg-slate-800 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                      >
                        {isSubmitting ? "Adding..." : "Add Property"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </main>
        )}
      </div>
    </div>
  );
}
