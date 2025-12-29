import React from "react";
import { test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AdminPanel } from "../AdminPanel";
import { useAuth } from "../AuthContext";
import * as api from "../../services/api";

vi.mock("../AuthContext");
vi.mock("../../services/api");

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.clearAllMocks();
});

test("no muestra panel admin por defecto (sin usuario admin)", () => {
  (
    useAuth as unknown as { mockReturnValue: (v: unknown) => void }
  ).mockReturnValue({ user: null });

  render(<AdminPanel />);
  const panelTitle = screen.queryByText(/Panel Admin/i);
  expect(panelTitle).toBeNull();
});

test("muestra panel compacto para usuario admin", async () => {
  (
    useAuth as unknown as { mockReturnValue: (v: unknown) => void }
  ).mockReturnValue({
    user: {
      id: "1",
      username: "admin",
      user_type: "employee",
      role: "admin",
      dlp_level: "standard",
      can_access_all_subjects: true,
      subject_ids: [],
    },
  });

  (
    api.listUsers as unknown as { mockResolvedValue: (v: unknown) => void }
  ).mockResolvedValue([
    {
      id: 1,
      username: "admin",
      user_type: "employee",
      role: "admin",
      dlp_level: "standard",
      is_active: true,
      can_access_all_subjects: true,
      subject_ids: [],
    },
  ]);

  (
    api.listAuditLog as unknown as { mockResolvedValue: (v: unknown) => void }
  ).mockResolvedValue([]);

  render(<AdminPanel />);

  // Debe mostrar título del panel compacto
  const title = await screen.findByText(/Panel Admin/i);
  expect(title).not.toBeNull();
});

test("no muestra panel admin para usuario customer", () => {
  (
    useAuth as unknown as { mockReturnValue: (v: unknown) => void }
  ).mockReturnValue({
    user: {
      id: "2",
      username: "cliente",
      user_type: "customer",
      role: "customer",
      dlp_level: "standard",
      can_access_all_subjects: false,
      subject_ids: ["CLI-00001"],
    },
  });

  render(<AdminPanel />);
  const panelTitle = screen.queryByText(/Panel Admin/i);
  expect(panelTitle).toBeNull();
});

test("no muestra panel admin para empleado no admin", () => {
  (
    useAuth as unknown as { mockReturnValue: (v: unknown) => void }
  ).mockReturnValue({
    user: {
      id: "3",
      username: "soporte",
      user_type: "employee",
      role: "support",
      dlp_level: "standard",
      can_access_all_subjects: false,
      subject_ids: [],
    },
  });

  render(<AdminPanel />);
  const panelTitle = screen.queryByText(/Panel Admin/i);
  expect(panelTitle).toBeNull();
});
