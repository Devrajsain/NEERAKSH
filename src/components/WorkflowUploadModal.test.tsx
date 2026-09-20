import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import * as api from '../services/api';

// Mock the API calls
vi.mock('../services/api', () => ({
  createCase: vi.fn(),
  getCase: vi.fn(),
  continueCaseFeature2: vi.fn(),
}));

describe('WorkflowUploadModal State Preservation and Progression', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.scrollTo = vi.fn() as any;
  });

  it('preserves state when transitioning to dashboard and handles synchronous COMPLETED correctly', async () => {
    // 1. Mock createCase returning COMPLETED synchronously
    const mockCaseResponse = {
      id: 'SLK-TEST1',
      status: 'COMPLETED',
      summary_json: {
        spill: { requires_coordinates: false },
        drift: { status: 'COMPLETED' },
        attribution_status: 'COMPLETED',
        bayesian_report: true,
      },
    };
    (api.createCase as any).mockResolvedValue(mockCaseResponse);

    // 2. Render App (starting at home view)
    render(<App />);

    // Wait for HeroSection's "Open Interactive Evidence Upload" button
    const openButtons = screen.getAllByText('Upload Evidence Case'); // Usually in HeroSection or Header
    const openButton = openButtons[0] || screen.getByText('Open Interactive Evidence Upload');
    fireEvent.click(openButton);

    // Modal should be open. Check for "Process Evidence Case"
    const file1 = new File(['dummy content'], 'synthetic_sentinel1_oil_spill_caseB.tif', { type: 'image/tiff' });
    const file2 = new File(['dummy content'], 'synthetic_ais_oil_spill_caseB_2026.csv', { type: 'text/csv' });

    // Assuming we have file inputs (they are hidden or styled, so we might need to find by test-id or label)
    const fileInputs = document.querySelectorAll('input[type="file"]');
    const imageInput = fileInputs[0] as HTMLInputElement;
    const csvInput = fileInputs[1] as HTMLInputElement;
    
    // Simulate user selecting files
    await userEvent.upload(imageInput, file1);
    await userEvent.upload(csvInput, file2);

    // Click "Synthetic Testing" checkbox if it exists
    const testModeCheckbox = document.getElementById('testModeCheckbox');
    if (testModeCheckbox) {
      fireEvent.click(testModeCheckbox);
    }

    // 3. Start workflow
    const processButton = screen.getByText('Process Evidence Case');
    fireEvent.click(processButton);

    // 4. Verify createCase was called
    await waitFor(() => {
      expect(api.createCase).toHaveBeenCalledTimes(1);
    });

    // 5. Verify UI advances to the correct completed state (Step 4) and does not unmount to Step 1
    // Step 4 header: "Step 4: AIS Telemetry Attribution"
    await waitFor(() => {
      expect(screen.getByText('Step 4: AIS Telemetry Attribution')).toBeInTheDocument();
    });

    // The modal should remain mounted and show "Pipeline complete!"
    expect(screen.getByText('Pipeline complete!')).toBeInTheDocument();
  });

  it('handles asynchronous PENDING/PROCESSING -> COMPLETED correctly', async () => {
    // 1. Mock createCase returning PROCESSING
    const pendingCaseResponse = {
      id: 'SLK-TEST2',
      status: 'PROCESSING',
      summary_json: {
        spill: { requires_coordinates: false },
      },
    };
    (api.createCase as any).mockResolvedValue(pendingCaseResponse);

    // Mock getCase returning COMPLETED after polling
    const completedCaseResponse = {
      id: 'SLK-TEST2',
      status: 'COMPLETED',
      summary_json: {
        spill: { requires_coordinates: false },
        drift: { status: 'COMPLETED' },
        attribution_status: 'COMPLETED',
        bayesian_report: true,
      },
    };
    (api.getCase as any).mockResolvedValueOnce(pendingCaseResponse).mockResolvedValueOnce(completedCaseResponse);

    render(<App />);

    const openButtons = screen.getAllByText('Upload Evidence Case');
    const openButton = openButtons[0] || screen.getByText('Open Interactive Evidence Upload');
    fireEvent.click(openButton);

    const file1 = new File(['dummy content'], 'synthetic_sentinel1_oil_spill_caseB.tif', { type: 'image/tiff' });
    const fileInputs = document.querySelectorAll('input[type="file"]');
    const imageInput = fileInputs[0] as HTMLInputElement;
    
    await userEvent.upload(imageInput, file1);

    const processButton = screen.getByText('Process Evidence Case');
    fireEvent.click(processButton);

    await waitFor(() => {
      expect(api.createCase).toHaveBeenCalledTimes(1);
    });

    // It should poll getCase
    await waitFor(() => {
      expect(api.getCase).toHaveBeenCalledTimes(2);
    }, { timeout: 5000 });

    // It should eventually reach Step 4
    await waitFor(() => {
      expect(screen.getByText('Step 4: AIS Telemetry Attribution')).toBeInTheDocument();
    });
  });
});
