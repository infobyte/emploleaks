"use client";

import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Employee } from "@/lib/api";
import EmployeeCard from "./EmployeeCard";
import { GripVertical } from "lucide-react";

function SortableEmployee({
  employee,
  onExclude,
  onDelete,
}: {
  employee: Employee;
  onExclude: () => void;
  onDelete: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: employee.employee_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="flex items-center gap-1">
      <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing p-1 text-text-tertiary hover:text-text-secondary">
        <GripVertical className="w-3.5 h-3.5" />
      </div>
      <div className="flex-1">
        <EmployeeCard employee={employee} onExclude={onExclude} onDelete={onDelete} compact />
      </div>
    </div>
  );
}

interface Props {
  department: string;
  employees: Employee[];
  onExclude: (id: number) => void;
  onDelete: (id: number) => void;
}

export default function DeptColumn({ department, employees, onExclude, onDelete }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: department });

  return (
    <div
      ref={setNodeRef}
      className={`bg-bg-secondary border rounded-xl min-w-[280px] max-w-[320px] flex flex-col transition-colors ${
        isOver ? "border-accent bg-accent/5" : "border-border"
      }`}
    >
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border">
        <h3 className="text-xs font-medium text-text-primary truncate uppercase tracking-wide">{department}</h3>
        <span className="text-[11px] text-text-secondary bg-bg-tertiary px-2 py-0.5 rounded-full font-medium">
          {employees.length}
        </span>
      </div>
      <SortableContext
        items={employees.map((e) => e.employee_id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="space-y-1.5 flex-1 min-h-[60px] overflow-y-auto max-h-[60vh] p-2">
          {employees.map((emp) => (
            <SortableEmployee
              key={emp.employee_id}
              employee={emp}
              onExclude={() => onExclude(emp.employee_id)}
              onDelete={() => onDelete(emp.employee_id)}
            />
          ))}
          {employees.length === 0 && (
            <p className="text-xs text-text-tertiary text-center py-6">
              Drop employees here
            </p>
          )}
        </div>
      </SortableContext>
    </div>
  );
}
