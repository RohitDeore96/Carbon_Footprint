/**
 * LogActivityForm — WCAG AAA compliant data entry form for carbon footprint activities.
 * Supports Transport, Energy, Diet, and Consumption categories with Zod v4 + react-hook-form validation.
 * Every input is explicitly linked to its label via htmlFor/id pairing.
 */

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  ActivityFormSchema,
  CONSUMPTION_DEFAULTS,
  DIET_DEFAULTS,
  ENERGY_DEFAULTS,
  TRANSPORT_DEFAULTS,
  type ActivityFormValues,
  type ConsumptionFormValues,
  type DietFormValues,
  type EnergyFormValues,
  type TransportFormValues,
} from '../../schemas/activity-form.schema';
import {
  apiClient,
  type ActivityEntry,
  type ApiError,
  type CarbonCalculationResponse,
} from '../../services/apiClient';
import type { ActivityCategory } from '../../types/activity';

// ---------------------------------------------------------------------------
// Type helpers
// ---------------------------------------------------------------------------

const CATEGORY_DEFAULTS: Record<ActivityCategory, ActivityFormValues> = {
  transport: TRANSPORT_DEFAULTS,
  energy: ENERGY_DEFAULTS,
  food: DIET_DEFAULTS,
  consumption: CONSUMPTION_DEFAULTS,
};

// ---------------------------------------------------------------------------
// Sub-component prop interfaces
// ---------------------------------------------------------------------------

interface FieldErrorProps {
  readonly id: string;
  readonly message?: string;
}

interface FormSectionProps {
  readonly title: string;
  readonly headingId: string;
  readonly children: React.ReactNode;
}

interface CategoryFieldsProps {
  readonly register: ReturnType<typeof useForm<ActivityFormValues>>['register'];
  readonly errors: ReturnType<typeof useForm<ActivityFormValues>>['formState']['errors'];
}

interface LogActivityFormProps {
  readonly userId: string;
  readonly onSuccess: (result: CarbonCalculationResponse) => void;
}

// ---------------------------------------------------------------------------
// Atomic sub-components
// ---------------------------------------------------------------------------

function FieldError({ id, message }: FieldErrorProps): React.JSX.Element | null {
  if (message === undefined || message === '') return null;
  return (
    <span id={id} role="alert" className="form-field-error" aria-live="assertive">
      {message}
    </span>
  );
}

function FormSection({ title, headingId, children }: FormSectionProps): React.JSX.Element {
  return (
    <section aria-labelledby={headingId} className="form-section">
      <h3 id={headingId} className="form-section-title">
        {title}
      </h3>
      {children}
    </section>
  );
}

function SubmitButton({ isSubmitting }: { readonly isSubmitting: boolean }): React.JSX.Element {
  return (
    <button
      type="submit"
      disabled={isSubmitting}
      aria-busy={isSubmitting}
      aria-label={isSubmitting ? 'Submitting activity entry…' : 'Log activity entry'}
      className="form-submit-btn"
      id="log-activity-submit-btn"
    >
      {isSubmitting ? (
        <span role="status" aria-live="polite" className="btn-loading-text">
          <span className="loading-spinner btn-spinner" aria-hidden="true" />
          Submitting…
        </span>
      ) : (
        'Log Activity'
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Category-specific field groups
// ---------------------------------------------------------------------------

function TransportFields({ register, errors }: CategoryFieldsProps): React.JSX.Element {
  const errs = errors as ReturnType<typeof useForm<TransportFormValues>>['formState']['errors'];
  return (
    <FormSection title="Transport Details" headingId="transport-details-heading">
      <div className="form-field">
        <label htmlFor="transport-mode" className="form-label">
          Transport Mode <span aria-hidden="true" className="required-mark">*</span>
          <span className="sr-only">(required)</span>
        </label>
        <select
          id="transport-mode"
          className="form-select"
          aria-describedby="transport-mode-error"
          aria-required="true"
          {...register('mode')}
        >
          <option value="car">Car</option>
          <option value="bus">Bus</option>
          <option value="train">Train</option>
          <option value="bicycle">Bicycle</option>
          <option value="walking">Walking</option>
          <option value="flight">Flight</option>
        </select>
        <FieldError id="transport-mode-error" message={errs.mode?.message} />
      </div>
      <div className="form-field">
        <label htmlFor="transport-distance" className="form-label">
          Distance (km) <span aria-hidden="true" className="required-mark">*</span>
          <span className="sr-only">(required)</span>
        </label>
        <input
          id="transport-distance"
          type="number"
          min={0.1}
          max={50000}
          step={0.1}
          className="form-input"
          aria-describedby="transport-distance-error"
          aria-required="true"
          placeholder="e.g. 25.5"
          {...register('distance_km', { valueAsNumber: true })}
        />
        <FieldError id="transport-distance-error" message={errs.distance_km?.message} />
      </div>
    </FormSection>
  );
}

function EnergyFields({ register, errors }: CategoryFieldsProps): React.JSX.Element {
  const errs = errors as ReturnType<typeof useForm<EnergyFormValues>>['formState']['errors'];
  return (
    <FormSection title="Energy Details" headingId="energy-details-heading">
      <div className="form-field">
        <label htmlFor="energy-source" className="form-label">
          Energy Source <span aria-hidden="true" className="required-mark">*</span>
          <span className="sr-only">(required)</span>
        </label>
        <select
          id="energy-source"
          className="form-select"
          aria-describedby="energy-source-error"
          aria-required="true"
          {...register('source')}
        >
          <option value="electricity">Electricity</option>
          <option value="natural_gas">Natural Gas</option>
          <option value="solar">Solar</option>
          <option value="wind">Wind</option>
        </select>
        <FieldError id="energy-source-error" message={errs.source?.message} />
      </div>
      <div className="form-field">
        <label htmlFor="energy-consumption" className="form-label">
          Consumption (kWh) <span aria-hidden="true" className="required-mark">*</span>
          <span className="sr-only">(required)</span>
        </label>
        <input
          id="energy-consumption"
          type="number"
          min={0}
          max={1000000}
          step={0.1}
          className="form-input"
          aria-describedby="energy-consumption-error"
          aria-required="true"
          placeholder="e.g. 350"
          {...register('consumption_kwh', { valueAsNumber: true })}
        />
        <FieldError id="energy-consumption-error" message={errs.consumption_kwh?.message} />
      </div>
    </FormSection>
  );
}

function DietFields({ register, errors }: CategoryFieldsProps): React.JSX.Element {
  const errs = errors as ReturnType<typeof useForm<DietFormValues>>['formState']['errors'];
  return (
    <FormSection title="Diet Details" headingId="diet-details-heading">
      <div className="form-field">
        <label htmlFor="diet-type" className="form-label">
          Diet Type <span aria-hidden="true" className="required-mark">*</span>
          <span className="sr-only">(required)</span>
        </label>
        <select
          id="diet-type"
          className="form-select"
          aria-describedby="diet-type-error"
          aria-required="true"
          {...register('diet_type')}
        >
          <option value="meat_heavy">Meat Heavy</option>
          <option value="average">Average</option>
          <option value="vegetarian">Vegetarian</option>
          <option value="vegan">Vegan</option>
        </select>
        <FieldError id="diet-type-error" message={errs.diet_type?.message} />
      </div>
      <div className="form-field">
        <label htmlFor="diet-days" className="form-label">
          Number of Days <span aria-hidden="true" className="required-mark">*</span>
          <span className="sr-only">(required)</span>
        </label>
        <input
          id="diet-days"
          type="number"
          min={1}
          max={365}
          step={1}
          className="form-input"
          aria-describedby="diet-days-error"
          aria-required="true"
          placeholder="e.g. 7"
          {...register('days', { valueAsNumber: true })}
        />
        <FieldError id="diet-days-error" message={errs.days?.message} />
      </div>
    </FormSection>
  );
}

function ConsumptionFields({ register, errors }: CategoryFieldsProps): React.JSX.Element {
  const errs = errors as ReturnType<typeof useForm<ConsumptionFormValues>>['formState']['errors'];
  return (
    <FormSection title="Consumption Details" headingId="consumption-details-heading">
      <div className="form-field">
        <label htmlFor="consumption-item-type" className="form-label">
          Item Type <span aria-hidden="true" className="required-mark">*</span>
          <span className="sr-only">(required)</span>
        </label>
        <select
          id="consumption-item-type"
          className="form-select"
          aria-describedby="consumption-item-type-error"
          aria-required="true"
          {...register('item_type')}
        >
          <option value="clothing">Clothing</option>
          <option value="electronics">Electronics</option>
          <option value="furniture">Furniture</option>
          <option value="general">General</option>
        </select>
        <FieldError id="consumption-item-type-error" message={errs.item_type?.message} />
      </div>
      <div className="form-field">
        <label htmlFor="consumption-quantity" className="form-label">
          Quantity <span aria-hidden="true" className="required-mark">*</span>
          <span className="sr-only">(required)</span>
        </label>
        <input
          id="consumption-quantity"
          type="number"
          min={1}
          max={1000}
          step={1}
          className="form-input"
          aria-describedby="consumption-quantity-error"
          aria-required="true"
          placeholder="e.g. 3"
          {...register('quantity', { valueAsNumber: true })}
        />
        <FieldError id="consumption-quantity-error" message={errs.quantity?.message} />
      </div>
    </FormSection>
  );
}

// ---------------------------------------------------------------------------
// Payload builder
// ---------------------------------------------------------------------------

function ensureDateString(dateStr: string): string {
  // datetime-local inputs return "YYYY-MM-DDTHH:MM" (no seconds),
  // but the backend requires "YYYY-MM-DDTHH:MM:SS".
  return dateStr.length === 16 ? `${dateStr}:00` : dateStr;
}

function buildActivityEntry(values: ActivityFormValues): ActivityEntry {
  const base = { category: values.category, description: values.description, date: ensureDateString(values.date) };
  if (values.category === 'transport') {
    return { ...base, transport: { mode: values.mode, distance_km: values.distance_km } };
  }
  if (values.category === 'energy') {
    return { ...base, energy: { source: values.source, consumption_kwh: values.consumption_kwh } };
  }
  if (values.category === 'consumption') {
    return { ...base, consumption: { item_type: values.item_type, quantity: values.quantity } };
  }
  return { ...base, diet: { diet_type: values.diet_type, days: values.days } };
}

// ---------------------------------------------------------------------------
// Main form component
// ---------------------------------------------------------------------------

export function LogActivityForm({ userId, onSuccess }: LogActivityFormProps): React.JSX.Element {
  const [selectedCategory, setSelectedCategory] = useState<ActivityCategory>('transport');
  const [apiError, setApiError] = useState<ApiError | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ActivityFormValues>({
    resolver: zodResolver(ActivityFormSchema),
    defaultValues: TRANSPORT_DEFAULTS,
  });

  const onSubmit = async (values: ActivityFormValues): Promise<void> => {
    setApiError(null);
    const entry = buildActivityEntry(values);
    const result = await apiClient.postFootprintLog({
      user_id: userId,
      entries: [entry],
      calculation_date: new Date().toISOString().slice(0, 19),
    });
    if (result.success) {
      reset(CATEGORY_DEFAULTS[selectedCategory]);
      onSuccess(result.data);
    } else {
      setApiError(result.error);
    }
  };

  const handleCategoryChange = (event: React.ChangeEvent<HTMLSelectElement>): void => {
    const next = event.target.value as ActivityCategory;
    setSelectedCategory(next);
    reset(CATEGORY_DEFAULTS[next]);
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      noValidate
      aria-label="Log a carbon footprint activity"
      className="log-activity-form"
      id="log-activity-form"
    >
      <FormSection title="Activity Details" headingId="activity-details-heading">
        <div className="form-field">
          <label htmlFor="activity-category" className="form-label">
            Category <span aria-hidden="true" className="required-mark">*</span>
            <span className="sr-only">(required)</span>
          </label>
          <select
            id="activity-category"
            className="form-select"
            aria-required="true"
            aria-describedby="category-hint"
            value={selectedCategory}
            onChange={handleCategoryChange}
          >
            <option value="transport">Transportation</option>
            <option value="energy">Energy</option>
            <option value="food">Diet / Food</option>
            <option value="consumption">Consumption</option>
          </select>
          <span id="category-hint" className="form-hint">
            Choose the type of activity to log
          </span>
        </div>

        <div className="form-field">
          <label htmlFor="activity-description" className="form-label">
            Description <span aria-hidden="true" className="required-mark">*</span>
            <span className="sr-only">(required)</span>
          </label>
          <input
            id="activity-description"
            type="text"
            className="form-input"
            aria-required="true"
            aria-describedby="activity-description-error activity-description-hint"
            placeholder="e.g. Daily commute to office"
            maxLength={500}
            {...register('description')}
          />
          <span id="activity-description-hint" className="form-hint">
            Max 500 characters
          </span>
          <FieldError id="activity-description-error" message={errors.description?.message} />
        </div>

        <div className="form-field">
          <label htmlFor="activity-date" className="form-label">
            Date <span aria-hidden="true" className="required-mark">*</span>
            <span className="sr-only">(required)</span>
          </label>
          <input
            id="activity-date"
            type="datetime-local"
            className="form-input"
            aria-required="true"
            aria-describedby="activity-date-error"
            {...register('date')}
          />
          <FieldError id="activity-date-error" message={errors.date?.message} />
        </div>
      </FormSection>

      {selectedCategory === 'transport' && (
        <TransportFields register={register} errors={errors} />
      )}
      {selectedCategory === 'energy' && (
        <EnergyFields register={register} errors={errors} />
      )}
      {selectedCategory === 'food' && (
        <DietFields register={register} errors={errors} />
      )}
      {selectedCategory === 'consumption' && (
        <ConsumptionFields register={register} errors={errors} />
      )}

      {apiError !== null && (
        <div role="alert" className="form-api-error" aria-live="assertive" id="form-api-error">
          <strong>Submission failed ({apiError.code}):</strong>{' '}
          {apiError.detail ?? apiError.message}
        </div>
      )}

      <SubmitButton isSubmitting={isSubmitting} />
    </form>
  );
}
