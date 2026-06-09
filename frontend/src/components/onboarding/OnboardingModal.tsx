/**
 * OnboardingModal — A 3-step welcome modal for first-time users.
 * Tracks completion via localStorage key 'carbon-footprint-onboarding-complete'.
 * Only renders when the key does not exist.
 * Implements basic focus trapping and accessibility attributes.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'carbon-footprint-onboarding-complete';

interface OnboardingStep {
  readonly icon: string;
  readonly title: string;
  readonly description: string;
}

const STEPS: readonly OnboardingStep[] = [
  {
    icon: '\u{1F30D}',
    title: 'Welcome to Carbon Footprint Tracker',
    description:
      'Track your daily carbon emissions across transport, energy, diet, and consumption categories.',
  },
  {
    icon: '\u{1F4DD}',
    title: 'Log Your First Activity',
    description:
      'Start by recording your daily activities \u2014 car commutes, electricity usage, meals, and purchases.',
  },
  {
    icon: '\u2726',
    title: 'Get AI-Powered Insights',
    description:
      'Our AI coach analyzes your data and provides personalized recommendations to reduce your carbon footprint.',
  },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OnboardingModal(): React.JSX.Element | null {
  const [visible, setVisible] = useState(() => {
    const completed = localStorage.getItem(STORAGE_KEY);
    return completed !== 'true';
  });
  const [currentStep, setCurrentStep] = useState(0);
  const modalRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Store previously focused element & auto-focus modal
  useEffect(() => {
    if (visible) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      // Focus the modal container after render
      const timer = setTimeout(() => {
        modalRef.current?.focus();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [visible]);

  // Basic focus trap
  useEffect(() => {
    if (!visible) return;

    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key !== 'Tab') return;

      const modal = modalRef.current;
      if (!modal) return;

      const focusable = modal.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [visible]);

  const completeOnboarding = useCallback((): void => {
    localStorage.setItem(STORAGE_KEY, 'true');
    setVisible(false);
    // Restore previous focus
    previousFocusRef.current?.focus();
  }, []);

  const handleNext = useCallback((): void => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep]);

  const handlePrevious = useCallback((): void => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  }, [currentStep]);

  const handleSkip = useCallback((): void => {
    completeOnboarding();
  }, [completeOnboarding]);

  const isLastStep = currentStep === STEPS.length - 1;
  const step = STEPS[currentStep];

  if (!visible) return null;

  return (
    <div className="onboarding-overlay" onClick={handleSkip}>
      <div
        className="onboarding-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-step-title"
        ref={modalRef}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Step content */}
        <div className="onboarding-step">
          <span className="onboarding-step-icon" aria-hidden="true">
            {step.icon}
          </span>
          <h2 id="onboarding-step-title" className="onboarding-step-title">
            {step.title}
          </h2>
          <p className="onboarding-step-description">{step.description}</p>
        </div>

        {/* Progress dots */}
        <div className="onboarding-dots" role="tablist" aria-label="Onboarding progress">
          {STEPS.map((_, index) => (
            <span
              key={index}
              className={`onboarding-dot ${index === currentStep ? 'onboarding-dot--active' : ''} ${index < currentStep ? 'onboarding-dot--completed' : ''}`}
              role="tab"
              aria-selected={index === currentStep}
              aria-label={`Step ${index + 1} of ${STEPS.length}`}
            />
          ))}
        </div>

        {/* Navigation */}
        <div className="onboarding-nav">
          <button
            type="button"
            className="onboarding-btn onboarding-btn--skip"
            onClick={handleSkip}
          >
            Skip
          </button>

          <div className="onboarding-nav-right">
            {currentStep > 0 && (
              <button
                type="button"
                className="onboarding-btn onboarding-btn--previous"
                onClick={handlePrevious}
              >
                Previous
              </button>
            )}

            {isLastStep ? (
              <button
                type="button"
                className="onboarding-btn onboarding-btn--start"
                onClick={completeOnboarding}
              >
                Get Started
              </button>
            ) : (
              <button
                type="button"
                className="onboarding-btn onboarding-btn--next"
                onClick={handleNext}
              >
                Next
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
