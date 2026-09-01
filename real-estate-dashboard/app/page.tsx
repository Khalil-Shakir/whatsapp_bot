"use client";

import React, { useState, useEffect } from "react";
import { 
  Building2, 
  Users, 
  Search, 
  Plus, 
  MessageSquare, 
  Trash2, 
  ExternalLink,
  CheckCircle2,
  TrendingUp,
  Filter
} from "lucide-react";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer 
} from "recharts";

// Interfaces mirroring backend models
interface Lead {
  id: number;
  phone: string;
  name: string;
  intent: "BUY" | "SELL" | "BOTH";
  status: string;
  budget_max?: number;
  area?: string;
}

interface Property {
  id: number;
  title: string;
  price: number;
  area: string;
  bedrooms: number;
  status: "AVAILABLE" | "SOLD";
}

const API_BASE = "http://localhost:8000"; // FastAPI endpoint

export default function RealEstateDashboard() {
  const [activeTab, setActiveTab] = useState<"overview" | "leads" | "properties" | "matches">("overview");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [searchTerm, setSearchTerm] = useState("");

  // Initial Fetching
  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [leadsRes, propsRes] = await Promise.all([
        fetch(`${API_BASE}/leads`).then((res) => res.json()),
        fetch(`${API_BASE}/properties`).then((res) => res.json()),
      ]);
      setLeads(leadsRes);
      setProperties(propsRes);
    } catch (error) {
      console.error("Failed to connect to FastAPI backend:", error);
    }
  };

  const handleUpdateStatus = async (propertyId: number, status: "AVAILABLE" | "SOLD") => {
    await fetch(`${API_BASE}/properties/${propertyId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    fetchData();
  };

  const chartData = [
    { name: "Buyers", count: leads.filter((l) => l.intent === "BUY").length },
    { name: "Sellers", count: leads.filter((l) => l.intent === "SELL").length },
    { name: "Dual Intent", count: leads.filter((l) => l.intent === "BOTH").length },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex font-sans">
      {/* Sidebar Navigation */}
      <aside className="w-64 border-r border-slate-800 bg-slate-900/50 p-6 flex flex-col justify-between">
        <div>
          <div className="flex items-center gap-3 mb-8">
            <div className="p-2 bg-indigo-600 rounded-lg text-white">
              <Building2 className="w-6 h-6" />
            </div>
            <h1 className="font-bold text-lg tracking-wide text-slate-100">EstateBot AI</h1>
          </div>

          <nav className="space-y-2">
            {[
              { id: "overview", label: "Overview", icon: TrendingUp },
              { id: "leads", label: "Leads Directory", icon: Users },
              { id: "properties", label: "Properties", icon: Building2 },
              { id: "matches", label: "Auto-Match", icon: Filter },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id as any)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-medium text-sm transition-all ${
                    activeTab === item.id
                      ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                      : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="p-4 bg-slate-800/40 border border-slate-800 rounded-xl text-xs text-slate-400">
          <p className="font-semibold text-slate-200 mb-1">WhatsApp Agent</p>
          <div className="flex items-center gap-2 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Active & Listening
          </div>
        </div>
      </aside>

      {/* Main Workspace */}
      <main className="flex-1 p-8 overflow-y-auto">
        {/* Top Header */}
        <header className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-100 capitalize">{activeTab}</h2>
            <p className="text-sm text-slate-400">Manage real estate inventory & client intents</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" />
              <input
                type="text"
                placeholder="Search phone, area, name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-indigo-500 w-64"
              />
            </div>
          </div>
        </header>

        {/* Tab Content: Overview */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            <div className="grid grid-cols-3 gap-6">
              <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800">
                <p className="text-sm text-slate-400">Total Leads Captured</p>
                <h3 className="text-3xl font-bold text-slate-100 mt-2">{leads.length}</h3>
              </div>
              <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800">
                <p className="text-sm text-slate-400">Active Properties</p>
                <h3 className="text-3xl font-bold text-slate-100 mt-2">
                  {properties.filter((p) => p.status === "AVAILABLE").length}
                </h3>
              </div>
              <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800">
                <p className="text-sm text-slate-400">Units Sold</p>
                <h3 className="text-3xl font-bold text-emerald-400 mt-2">
                  {properties.filter((p) => p.status === "SOLD").length}
                </h3>
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800">
              <h3 className="text-lg font-semibold text-slate-200 mb-4">Lead Breakdown</h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <XAxis dataKey="name" stroke="#64748b" />
                    <YAxis stroke="#64748b" />
                    <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                    <Bar dataKey="count" fill="#6366f1" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {/* Tab Content: Leads */}
        {activeTab === "leads" && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <table className="w-full text-left border-collapse text-sm">
              <thead className="bg-slate-800/50 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="p-4">Contact</th>
                  <th className="p-4">Intent</th>
                  <th className="p-4">Location</th>
                  <th className="p-4">Max Budget</th>
                  <th className="p-4">Quick Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {leads
                  .filter((l) => l.name?.toLowerCase().includes(searchTerm.toLowerCase()) || l.phone.includes(searchTerm))
                  .map((lead) => (
                    <tr key={lead.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="p-4 font-medium text-slate-200">
                        {lead.name || "Unknown"}
                        <span className="block text-xs text-slate-500">{lead.phone}</span>
                      </td>
                      <td className="p-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                          lead.intent === "BUY" ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        }`}>
                          {lead.intent}
                        </span>
                      </td>
                      <td className="p-4 text-slate-300">{lead.area || "N/A"}</td>
                      <td className="p-4 text-slate-300">
                        {lead.budget_max ? `$${lead.budget_max.toLocaleString()}` : "N/A"}
                      </td>
                      <td className="p-4">
                        <a
                          href={`https://wa.me/${lead.phone.replace(/[^0-9]/g, "")}`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 text-xs text-emerald-400 hover:underline"
                        >
                          <MessageSquare className="w-3.5 h-3.5" /> Chat on WhatsApp
                        </a>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab Content: Properties */}
        {activeTab === "properties" && (
          <div className="grid grid-cols-2 gap-6">
            {properties.map((property) => (
              <div key={property.id} className="bg-slate-900 border border-slate-800 p-6 rounded-2xl flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="font-bold text-lg text-slate-100">{property.title}</h3>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                      property.status === "AVAILABLE" ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800 text-slate-500"
                    }`}>
                      {property.status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-400 mb-4">{property.area} • {property.bedrooms} Bed</p>
                  <p className="text-2xl font-bold text-indigo-400">${property.price.toLocaleString()}</p>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-800 flex justify-end gap-3">
                  {property.status === "AVAILABLE" ? (
                    <button
                      onClick={() => handleUpdateStatus(property.id, "SOLD")}
                      className="px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600 text-emerald-300 hover:text-white border border-emerald-500/30 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" /> Mark as Sold
                    </button>
                  ) : (
                    <button
                      onClick={() => handleUpdateStatus(property.id, "AVAILABLE")}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition-all"
                    >
                      Re-list Property
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}