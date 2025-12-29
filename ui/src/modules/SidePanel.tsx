import React from "react";
import { SubjectContextPanel } from "./SubjectContextPanel";
import { CustomerSnapshotPanel } from "./CustomerSnapshotPanel";

interface SidePanelProps {
  subjectId: string | null;
  userType: string;
  onSubjectsChanged?: () => void;
}

export const SidePanel: React.FC<SidePanelProps> = ({
  subjectId,
  userType,
  onSubjectsChanged,
}) => {
  // onSubjectsChanged se mantiene en la firma para compatibilidad pero ya no se usa aquí
  void onSubjectsChanged;
  return (
    <aside className="side-panel">
      <SubjectContextPanel subjectId={subjectId} userType={userType} />
      <CustomerSnapshotPanel subjectId={subjectId} />
    </aside>
  );
};
