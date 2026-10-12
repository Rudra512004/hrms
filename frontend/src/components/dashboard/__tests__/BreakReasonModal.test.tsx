import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BreakReasonModal, BREAK_REASON_OPTIONS } from '../BreakReasonModal';

describe('BreakReasonModal (Phase 16N)', () => {
  const onClose = vi.fn();
  const onSubmit = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not render when isOpen is false', () => {
    render(
      <BreakReasonModal
        isOpen={false}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );
    expect(screen.queryByText('What is the break for?')).not.toBeInTheDocument();
  });

  it('renders modal header, subtitle, and close button when isOpen is true', () => {
    render(
      <BreakReasonModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    expect(screen.getByText('What is the break for?')).toBeInTheDocument();
    expect(screen.getByText('Choose the reason that best matches your time away.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /close dialog/i })).toBeInTheDocument();
  });

  it('renders all 10 reasons with exact labels and descriptions', () => {
    render(
      <BreakReasonModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    BREAK_REASON_OPTIONS.forEach((opt) => {
      expect(screen.getByText(opt.label)).toBeInTheDocument();
      expect(screen.getByText(opt.description)).toBeInTheDocument();
      expect(screen.getAllByText(opt.limitLabel).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('defaults to Lunch and displays 6 Counts as worked time indicators', () => {
    render(
      <BreakReasonModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    // Lunch radio should be checked
    const lunchOption = screen.getByRole('radio', { name: /Lunch/i });
    expect(lunchOption).toHaveAttribute('aria-checked', 'true');

    // Exactly 6 options have "Counts as worked time" indicator
    const workedTimeBadges = screen.getAllByText(/Counts as worked time/i);
    expect(workedTimeBadges).toHaveLength(6);
  });

  it('submits default Lunch when Start the break is clicked', async () => {
    onSubmit.mockResolvedValueOnce(undefined);

    render(
      <BreakReasonModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Start the break/i });
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('lunch', undefined);
    });
  });

  it('allows selecting another reason (e.g. Outside meeting) and submitting', async () => {
    onSubmit.mockResolvedValueOnce(undefined);

    render(
      <BreakReasonModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    const outsideMeetingOption = screen.getByRole('radio', { name: /Outside meeting/i });
    fireEvent.click(outsideMeetingOption);
    expect(outsideMeetingOption).toHaveAttribute('aria-checked', 'true');

    const submitBtn = screen.getByRole('button', { name: /Start the break/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('outside_meeting', undefined);
    });
  });

  it('requires trimmed comment of at least 3 characters when Other is selected', async () => {
    onSubmit.mockResolvedValueOnce(undefined);

    render(
      <BreakReasonModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    // Select Other
    const otherOption = screen.getByRole('radio', { name: /Other/i });
    fireEvent.click(otherOption);

    // Comment field appears
    const textarea = screen.getByPlaceholderText(/Say what the break is for/i);
    expect(textarea).toBeInTheDocument();

    const submitBtn = screen.getByRole('button', { name: /Start the break/i });
    // Empty comment -> button disabled
    expect(submitBtn).toBeDisabled();

    // Type 2 chars -> still disabled, shows helper warning
    fireEvent.change(textarea, { target: { value: 'ab' } });
    expect(screen.getByText(/Comment must be at least 3 characters/i)).toBeInTheDocument();
    expect(submitBtn).toBeDisabled();

    // Type valid comment -> enabled
    fireEvent.change(textarea, { target: { value: 'Doctor visit' } });
    expect(screen.queryByText(/Comment must be at least 3 characters/i)).not.toBeInTheDocument();
    expect(submitBtn).not.toBeDisabled();

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('other', 'Doctor visit');
    });
  });

  it('preserves selection and displays error banner when submission fails', async () => {
    onSubmit.mockRejectedValueOnce({
      errorData: { detail: 'Already on a break.' },
    });

    render(
      <BreakReasonModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    // Select Tea or coffee
    const coffeeOption = screen.getByRole('radio', { name: /Tea or coffee/i });
    fireEvent.click(coffeeOption);

    const submitBtn = screen.getByRole('button', { name: /Start the break/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Already on a break.');
    });

    // Selection remains Tea or coffee
    expect(coffeeOption).toHaveAttribute('aria-checked', 'true');
    // onClose was not called
    expect(onClose).not.toHaveBeenCalled();
  });

  it('prevents duplicate submissions while loading', async () => {
    let resolveSubmit: () => void;
    const submitPromise = new Promise<void>((resolve) => {
      resolveSubmit = resolve;
    });
    onSubmit.mockReturnValue(submitPromise);

    render(
      <BreakReasonModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Start the break/i });
    fireEvent.click(submitBtn);
    fireEvent.click(submitBtn);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Starting.../i)).toBeInTheDocument();

    await waitFor(() => {
      resolveSubmit!();
    });
  });

  it('does not start a break when closing or clicking Cancel', () => {
    render(
      <BreakReasonModal
        isOpen={true}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onSubmit).not.toHaveBeenCalled();

    const closeBtn = screen.getByRole('button', { name: /close dialog/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(2);
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
