/**
 * Shared type definitions for activity categories and related data.
 * Single source of truth — eliminates duplicate definitions across components.
 */

export type ActivityCategory = 'transport' | 'energy' | 'food' | 'consumption';

export type TransportMode = 'car' | 'bus' | 'train' | 'bicycle' | 'walking' | 'flight';
export type EnergySource = 'electricity' | 'natural_gas' | 'solar' | 'wind';
export type DietType = 'meat_heavy' | 'average' | 'vegetarian' | 'vegan';
export type ConsumptionItemType = 'clothing' | 'electronics' | 'furniture' | 'general';
