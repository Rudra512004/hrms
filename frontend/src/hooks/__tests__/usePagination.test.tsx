import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import { usePagination } from '../usePagination';

describe('usePagination hook', () => {
  const createWrapper = (initialEntries: string[] = ['/']) => {
    return ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter initialEntries={initialEntries}>
        {children}
      </MemoryRouter>
    );
  };

  it('initializes with default page 1 and page_size 20', () => {
    const { result } = renderHook(() => usePagination(), {
      wrapper: createWrapper(),
    });

    expect(result.current.page).toBe(1);
    expect(result.current.pageSize).toBe(20);
    expect(result.current.totalCount).toBe(0);
  });

  it('reads initial page and page_size from URL query params', () => {
    const { result } = renderHook(() => usePagination(), {
      wrapper: createWrapper(['/employees?page=3&page_size=50']),
    });

    expect(result.current.page).toBe(3);
    expect(result.current.pageSize).toBe(50);
  });

  it('updates page and totalCount correctly', () => {
    const { result } = renderHook(() => usePagination(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.handlePageChange(2);
      result.current.setTotalCount(45);
    });

    expect(result.current.page).toBe(2);
    expect(result.current.totalCount).toBe(45);
  });

  it('resets page to 1 on resetPage call', () => {
    const { result } = renderHook(() => usePagination(), {
      wrapper: createWrapper(['/employees?page=4']),
    });

    expect(result.current.page).toBe(4);

    act(() => {
      result.current.resetPage();
    });

    expect(result.current.page).toBe(1);
  });

  it('handles negative or invalid URL page numbers by defaulting to 1', () => {
    const { result } = renderHook(() => usePagination(), {
      wrapper: createWrapper(['/employees?page=-5']),
    });

    expect(result.current.page).toBe(1);
  });
});
