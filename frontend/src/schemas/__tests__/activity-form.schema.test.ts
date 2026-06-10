import { describe, it, expect } from 'vitest';
import {
  TransportFormSchema,
  EnergyFormSchema,
  DietFormSchema,
  ConsumptionFormSchema,
  ActivityFormSchema,
} from '../activity-form.schema';

describe('ActivityFormSchema', () => {
  describe('TransportFormSchema', () => {
    it('validates valid transport data', () => {
      const result = TransportFormSchema.safeParse({
        category: 'transport',
        description: 'Daily commute',
        date: '2026-06-09T10:00',
        mode: 'car',
        distance_km: 25,
      });
      expect(result.success).toBe(true);
    });

    it('rejects negative distance', () => {
      const result = TransportFormSchema.safeParse({
        category: 'transport',
        description: 'Daily commute',
        date: '2026-06-09T10:00',
        mode: 'car',
        distance_km: -5,
      });
      expect(result.success).toBe(false);
    });

    it('rejects empty description', () => {
      const result = TransportFormSchema.safeParse({
        category: 'transport',
        description: '',
        date: '2026-06-09T10:00',
        mode: 'car',
        distance_km: 25,
      });
      expect(result.success).toBe(false);
    });
  });

  describe('EnergyFormSchema', () => {
    it('validates valid energy data', () => {
      const result = EnergyFormSchema.safeParse({
        category: 'energy',
        description: 'Home electricity',
        date: '2026-06-09T10:00',
        source: 'electricity',
        consumption_kwh: 350,
      });
      expect(result.success).toBe(true);
    });

    it('rejects invalid energy source', () => {
      const result = EnergyFormSchema.safeParse({
        category: 'energy',
        description: 'Home electricity',
        date: '2026-06-09T10:00',
        source: 'nuclear',
        consumption_kwh: 350,
      });
      expect(result.success).toBe(false);
    });
  });

  describe('DietFormSchema', () => {
    it('validates valid diet data', () => {
      const result = DietFormSchema.safeParse({
        category: 'food',
        description: 'Weekly meals',
        date: '2026-06-09T10:00',
        diet_type: 'vegetarian',
        days: 7,
      });
      expect(result.success).toBe(true);
    });

    it('rejects zero days', () => {
      const result = DietFormSchema.safeParse({
        category: 'food',
        description: 'Weekly meals',
        date: '2026-06-09T10:00',
        diet_type: 'vegetarian',
        days: 0,
      });
      expect(result.success).toBe(false);
    });
  });

  describe('ConsumptionFormSchema', () => {
    it('validates valid consumption data', () => {
      const result = ConsumptionFormSchema.safeParse({
        category: 'consumption',
        description: 'Bought new clothes',
        date: '2026-06-09T10:00',
        item_type: 'clothing',
        quantity: 3,
      });
      expect(result.success).toBe(true);
    });

    it('rejects zero quantity', () => {
      const result = ConsumptionFormSchema.safeParse({
        category: 'consumption',
        description: 'Bought new clothes',
        date: '2026-06-09T10:00',
        item_type: 'clothing',
        quantity: 0,
      });
      expect(result.success).toBe(false);
    });
  });

  describe('ActivityFormSchema discriminated union', () => {
    it('validates transport category', () => {
      const result = ActivityFormSchema.safeParse({
        category: 'transport',
        description: 'Commute',
        date: '2026-06-09T10:00',
        mode: 'bus',
        distance_km: 15,
      });
      expect(result.success).toBe(true);
    });

    it('validates consumption category', () => {
      const result = ActivityFormSchema.safeParse({
        category: 'consumption',
        description: 'New laptop',
        date: '2026-06-09T10:00',
        item_type: 'electronics',
        quantity: 1,
      });
      expect(result.success).toBe(true);
    });

    it('rejects invalid category', () => {
      const result = ActivityFormSchema.safeParse({
        category: 'invalid',
        description: 'Test',
        date: '2026-06-09T10:00',
      });
      expect(result.success).toBe(false);
    });
  });
});
