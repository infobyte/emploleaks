"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { useCompanyId } from "../layout";
import { api, Employee } from "@/lib/api";
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
} from "@dnd-kit/core";
import DeptColumn from "@/components/DeptColumn";
import EmployeeCard from "@/components/EmployeeCard";
import { Search, Plus, Sparkles, RefreshCw, Globe } from "lucide-react";

export default function EmployeesPage() {
  const companyId = useCompanyId();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [newDept, setNewDept] = useState("");
  const [classifying, setClassifying] = useState(false);
  const [lookingUp, setLookingUp] = useState(false);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const load = useCallback(() => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    api
      .getEmployees(companyId)
      .then(setEmployees)
      .catch((e) => setError(e.message || "Failed to load employees"))
      .finally(() => setLoading(false));
  }, [companyId]);

  useEffect(() => { load(); }, [load]);

  const departments = useMemo(() => {
    const depts = new Set<string>();
    employees.forEach((e) => { if (e.department) depts.add(e.department); });
    return Array.from(depts).sort();
  }, [employees]);

  const hasDepts = departments.length > 0;
  const UNASSIGNED = "Unassigned";

  const grouped = useMemo(() => {
    const map: Record<string, Employee[]> = {};
    if (hasDepts) {
      map[UNASSIGNED] = [];
      departments.forEach((d) => (map[d] = []));
    }
    const lower = search.toLowerCase();
    employees.forEach((e) => {
      if (lower && !(e.name || "").toLowerCase().includes(lower) && !(e.title || "").toLowerCase().includes(lower)) return;
      if (hasDepts) {
        const key = e.department || UNASSIGNED;
        if (!map[key]) map[key] = [];
        map[key].push(e);
      }
    });
    return map;
  }, [employees, departments, hasDepts, search]);

  const filteredList = useMemo(() => {
    if (hasDepts) return [];
    const lower = search.toLowerCase();
    return employees.filter(
      (e) =>
        !lower ||
        (e.name || "").toLowerCase().includes(lower) ||
        (e.title || "").toLowerCase().includes(lower)
    );
  }, [employees, hasDepts, search]);

  const handleDragStart = (event: DragStartEvent) => setActiveId(event.active.id as number);

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = event;
    if (!over) return;
    const empId = active.id as number;
    const targetDept = String(over.id);
    if (departments.includes(targetDept) || targetDept === UNASSIGNED) {
      const newDeptValue = targetDept === UNASSIGNED ? "" : targetDept;
      try {
        await api.updateEmployee(empId, { department: newDeptValue });
        setEmployees((prev) =>
          prev.map((e) => e.employee_id === empId ? { ...e, department: newDeptValue || null } : e)
        );
      } catch { /* ignore */ }
    }
  };

  const handleExclude = async (id: number) => {
    const emp = employees.find((e) => e.employee_id === id);
    if (!emp) return;
    const newVal = emp.excluded ? 0 : 1;
    try {
      await api.updateEmployee(id, { excluded: newVal });
      setEmployees((prev) => prev.map((e) => (e.employee_id === id ? { ...e, excluded: newVal } : e)));
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this employee and all associated data?")) return;
    try {
      await api.deleteEmployee(id);
      setEmployees((prev) => prev.filter((e) => e.employee_id !== id));
    } catch { /* ignore */ }
  };

  const handleAddDept = async () => {
    if (!newDept.trim()) return;
    const unassigned = employees.filter((e) => !e.department);
    if (unassigned.length === 0) {
      const dummy = employees[0];
      if (dummy) {
        await api.updateEmployee(dummy.employee_id, { department: newDept.trim() });
        await api.updateEmployee(dummy.employee_id, { department: dummy.department || "" });
      }
    }
    setNewDept("");
    load();
  };

  const handleClassify = async () => {
    if (!companyId) return;
    setClassifying(true);
    try {
      await api.classifyEmployees(companyId);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Classification failed");
    } finally {
      setClassifying(false);
    }
  };

  const handleLookup = async () => {
    if (!companyId) return;
    setLookingUp(true);
    try {
      const result = await api.lookupSocialProfiles(companyId);
      load();
      alert(`Found ${result.found} social profiles across ${result.emails_checked} emails`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Lookup failed");
    } finally {
      setLookingUp(false);
    }
  };

  const activeEmployee = activeId ? employees.find((e) => e.employee_id === activeId) : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-sm text-text-secondary animate-pulse">Loading employees...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-sm text-danger mb-1">Error loading employees</p>
          <p className="text-xs text-text-secondary mb-3">{error}</p>
          <button onClick={load} className="inline-flex items-center gap-1.5 bg-accent text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors">
            <RefreshCw className="w-3 h-3" /> Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-full mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Employees</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            {employees.length} total{hasDepts ? " · Drag between departments" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {employees.length > 0 && (
            <button
              onClick={handleLookup}
              disabled={lookingUp}
              className="inline-flex items-center gap-1.5 bg-bg-secondary border border-border text-text-primary px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-bg-hover transition-colors disabled:opacity-50"
            >
              <Globe className="w-3.5 h-3.5" />
              {lookingUp ? "Looking up..." : "Lookup Social"}
            </button>
          )}
          {!hasDepts && employees.length > 0 && (
            <button
              onClick={handleClassify}
              disabled={classifying}
              className="inline-flex items-center gap-1.5 bg-accent text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {classifying ? "Classifying..." : "Classify with AI"}
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
          <input
            type="text"
            placeholder="Search by name or role..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-bg-secondary border border-border rounded-lg pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent transition-colors"
          />
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="New department..."
            value={newDept}
            onChange={(e) => setNewDept(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddDept()}
            className="bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent w-40 transition-colors"
          />
          <button
            onClick={handleAddDept}
            className="inline-flex items-center gap-1 bg-bg-secondary border border-border text-text-primary px-3 py-2 rounded-lg text-xs font-medium hover:bg-bg-hover transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add
          </button>
        </div>
      </div>

      {hasDepts ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div className="flex gap-3 overflow-x-auto pb-4">
            {Object.entries(grouped).map(([dept, emps]) => (
              <DeptColumn key={dept} department={dept} employees={emps} onExclude={handleExclude} onDelete={handleDelete} />
            ))}
          </div>
          <DragOverlay>
            {activeEmployee && <EmployeeCard employee={activeEmployee} compact />}
          </DragOverlay>
        </DndContext>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {filteredList.map((emp) => (
            <EmployeeCard
              key={emp.employee_id}
              employee={emp}
              onExclude={() => handleExclude(emp.employee_id)}
              onDelete={() => handleDelete(emp.employee_id)}
              onRefresh={load}
            />
          ))}
        </div>
      )}
    </div>
  );
}
