/**
 * Zod v4 compliant validation schemas for the LogActivityForm.
 * Uses Zod v4 error API: `error` (not `errorMap`), no `invalid_type_error`.
 */

import { z } from 'zod';

/** Returns the current local date/time in YYYY-MM-DDTHH:MM format for datetime-local inputs. */
function todayLocal(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  const h = String(now.getHours()).padStart(2, '0');
  const min = String(now.getMinutes()).padStart(2, '0');
  return `${y}-${m}-${d}T${h}:${min}`;
}

const _today = todayLocal();

/** Refinement: date must not be in the future. */
const notFutureDate = z.string().refine(
  (val) => new Date(val) <= new Date(),
  { message: 'Date cannot be in the future' },
);

/** Composable date field with future-date guard. */
const dateField = z.string().min(1, 'Date is required').pipe(notFutureDate);

export const TransportFormSchema = z.object({
  category: z.literal('transport'),
  description: z.string().min(1, 'Description is required').max(500, 'Max 500 characters'),
  date: dateField,
  mode: z.enum(['car', 'bus', 'train', 'bicycle', 'walking', 'flight'] as const, {
    error: 'Select a transport mode',
  }),
  distance_km: z
    .number()
    .min(0.1, 'Distance must be at least 0.1 km')
    .max(50000, 'Distance cannot exceed 50,000 km'),
});

export const EnergyFormSchema = z.object({
  category: z.literal('energy'),
  description: z.string().min(1, 'Description is required').max(500, 'Max 500 characters'),
  date: dateField,
  source: z.enum(['electricity', 'natural_gas', 'solar', 'wind'] as const, {
    error: 'Select an energy source',
  }),
  consumption_kwh: z
    .number()
    .nonnegative('Value must be 0 or greater')
    .max(1000000, 'Value exceeds maximum'),
});

export const DietFormSchema = z.object({
  category: z.literal('food'),
  description: z.string().min(1, 'Description is required').max(500, 'Max 500 characters'),
  date: dateField,
  diet_type: z.enum(['meat_heavy', 'average', 'vegetarian', 'vegan'] as const, {
    error: 'Select a diet type',
  }),
  days: z
    .number()
    .int('Days must be a whole number')
    .positive('Days must be at least 1')
    .max(365, 'Cannot exceed 365 days'),
});

export const ConsumptionFormSchema = z.object({
  category: z.literal('consumption'),
  description: z.string().min(1, 'Description is required').max(500, 'Max 500 characters'),
  date: dateField,
  item_type: z.enum(['clothing', 'electronics', 'furniture', 'general'] as const, {
    error: 'Select an item type',
  }),
  quantity: z
    .number()
    .int('Quantity must be a whole number')
    .positive('Quantity must be at least 1')
    .max(1000, 'Cannot exceed 1000 items'),
});

export const ActivityFormSchema = z.discriminatedUnion('category', [
  TransportFormSchema,
  EnergyFormSchema,
  DietFormSchema,
  ConsumptionFormSchema,
]);

export type TransportFormValues = z.infer<typeof TransportFormSchema>;
export type EnergyFormValues = z.infer<typeof EnergyFormSchema>;
export type DietFormValues = z.infer<typeof DietFormSchema>;
export type ConsumptionFormValues = z.infer<typeof ConsumptionFormSchema>;
export type ActivityFormValues = z.infer<typeof ActivityFormSchema>;

export const TRANSPORT_DEFAULTS: TransportFormValues = {
  category: 'transport',
  description: '',
  date: _today,
  mode: 'car',
  distance_km: 1,
};

export const ENERGY_DEFAULTS: EnergyFormValues = {
  category: 'energy',
  description: '',
  date: _today,
  source: 'electricity',
  consumption_kwh: 1,
};

export const DIET_DEFAULTS: DietFormValues = {
  category: 'food',
  description: '',
  date: _today,
  diet_type: 'average',
  days: 1,
};

export const CONSUMPTION_DEFAULTS: ConsumptionFormValues = {
  category: 'consumption',
  description: '',
  date: _today,
  item_type: 'general',
  quantity: 1,
};
