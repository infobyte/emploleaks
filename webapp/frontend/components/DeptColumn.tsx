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
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing">
      <EmployeeCard employee={employee} onExclude={onExclude} onDelete={onDelete} compact />
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
      className={`bg-bg-secondary border rounded-xl p-3 min-w-[280px] max-w-[320px] flex flex-col ${
        isOver ? "border-accent" : "border-border"
      }`}
    >
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 className="text-sm font-semibold text-text-primary truncate">{department}</h3>
        <span className="text-xs text-text-secondary bg-bg-tertiary px-2 py-0.5 rounded-full">
          {employees.length}
        </span>
      </div>
      <SortableContext
        items={employees.map((e) => e.employee_id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="space-y-2 flex-1 min-h-[80px] overflow-y-auto max-h-[60vh]">
          {employees.map((emp) => (
            <SortableEmployee
              key={emp.employee_id}
              employee={emp}
              onExclude={() => onExclude(emp.employee_id)}
              onDelete={() => onDelete(emp.employee_id)}
            />
          ))}
          {employees.length === 0 && (
            <p className="text-xs text-text-secondary text-center py-4">
              Drop employees here
            </p>
          )}
        </div>
      </SortableContext>
    </div>
  );
}
