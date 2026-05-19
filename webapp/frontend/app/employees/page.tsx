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
import DeptSection from "@/components/DeptSection";
import EmployeeCard from "@/components/EmployeeCard";
import { Search, Plus, Sparkles, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

const UNASSIGNED = "Unassigned";

export default function EmployeesPage() {
  const companyId = useCompanyId();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [newDept, setNewDept] = useState("");
  const [classifying, setClassifying] = useState(false);
  const [allExpanded, setAllExpanded] = useState(true);
  const [expandKey, setExpandKey] = useState(0);

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

  const grouped = useMemo(() => {
    const map: Record<string, Employee[]> = {};
    if (hasDepts) {
      departments.forEach((d) => (map[d] = []));
      map[UNASSIGNED] = [];
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

  const handleChangeDept = async (empId: number, dept: string) => {
    try {
      await api.updateEmployee(empId, { department: dept });
      setEmployees((prev) =>
        prev.map((e) => e.employee_id === empId ? { ...e, department: dept || null } : e)
      );
    } catch { /* ignore */ }
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

  const toggleAll = () => {
    setAllExpanded(!allExpanded);
    setExpandKey((k) => k + 1);
  };

  const activeEmployee = activeId ? employees.find((e) => e.employee_id === activeId) : null;

  const visibleSections = Object.entries(grouped).filter(([, emps]) => !search || emps.length > 0);
  const totalFiltered = visibleSections.reduce((sum, [, emps]) => sum + emps.length, 0);

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
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Employees</h1>
          <p className="text-sm text-text-secondary mt-0.5">
            {employees.length} total
            {hasDepts ? ` · ${departments.length} department${departments.length !== 1 ? "s" : ""}` : ""}
            {search && hasDepts ? ` · ${totalFiltered} matching` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
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
        <div className="relative flex-1 max-w-sm">
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
        {hasDepts && (
          <button
            onClick={toggleAll}
            className="inline-flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary transition-colors"
            title={allExpanded ? "Collapse all" : "Expand all"}
          >
            {allExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {allExpanded ? "Collapse" : "Expand"}
          </button>
        )}
      </div>

      {hasDepts ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div className="space-y-3">
            {visibleSections.map(([dept, emps]) => (
              <DeptSection
                key={`${dept}-${expandKey}`}
                department={dept}
                employees={emps}
                allDepartments={departments}
                onExclude={handleExclude}
                onDelete={handleDelete}
                onChangeDept={handleChangeDept}
                defaultExpanded={allExpanded}
              />
            ))}
          </div>
          <DragOverlay>
            {activeEmployee && (
              <div className="bg-bg-secondary border border-accent rounded-lg px-3 py-2 shadow-lg max-w-xs">
                <p className="text-sm font-medium text-text-primary truncate">{activeEmployee.name}</p>
                {activeEmployee.title && <p className="text-xs text-text-secondary truncate">{activeEmployee.title}</p>}
              </div>
            )}
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
