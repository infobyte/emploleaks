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

export default function EmployeesPage() {
  const companyId = useCompanyId();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [newDept, setNewDept] = useState("");

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const load = useCallback(() => {
    if (!companyId) return;
    setLoading(true);
    api
      .getEmployees(companyId)
      .then(setEmployees)
      .catch(() => {})
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

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as number);
  };

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
          prev.map((e) =>
            e.employee_id === empId ? { ...e, department: newDeptValue || null } : e
          )
        );
      } catch {}
    }
  };

  const handleExclude = async (id: number) => {
    const emp = employees.find((e) => e.employee_id === id);
    if (!emp) return;
    const newVal = emp.excluded ? 0 : 1;
    try {
      await api.updateEmployee(id, { excluded: newVal });
      setEmployees((prev) =>
        prev.map((e) => (e.employee_id === id ? { ...e, excluded: newVal } : e))
      );
    } catch {}
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this employee and all associated data?")) return;
    try {
      await api.deleteEmployee(id);
      setEmployees((prev) => prev.filter((e) => e.employee_id !== id));
    } catch {}
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

  const activeEmployee = activeId ? employees.find((e) => e.employee_id === activeId) : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-text-secondary">Loading employees...</div>
      </div>
    );
  }

  return (
    <div className="max-w-full mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold mb-1">Employee Management</h1>
          <p className="text-text-secondary text-sm">
            {employees.length} employees &middot;{" "}
            {hasDepts
              ? "Drag & drop between departments"
              : "Assign departments to enable Kanban view"}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search by name or role..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 max-w-sm bg-bg-tertiary border border-border rounded-lg px-4 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:border-accent"
        />
        {hasDepts && (
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="New department..."
              value={newDept}
              onChange={(e) => setNewDept(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddDept()}
              className="bg-bg-tertiary border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:border-accent w-48"
            />
            <button
              onClick={handleAddDept}
              className="bg-accent text-bg-primary px-3 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
            >
              Add Dept
            </button>
          </div>
        )}
      </div>

      {hasDepts ? (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-4 overflow-x-auto pb-4">
            {Object.entries(grouped).map(([dept, emps]) => (
              <DeptColumn
                key={dept}
                department={dept}
                employees={emps}
                onExclude={handleExclude}
                onDelete={handleDelete}
              />
            ))}
          </div>
          <DragOverlay>
            {activeEmployee && <EmployeeCard employee={activeEmployee} compact />}
          </DragOverlay>
        </DndContext>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredList.map((emp) => (
            <EmployeeCard
              key={emp.employee_id}
              employee={emp}
              onExclude={() => handleExclude(emp.employee_id)}
              onDelete={() => handleDelete(emp.employee_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
