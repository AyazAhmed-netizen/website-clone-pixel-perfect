"use client";

import { useState, useCallback, useEffect } from "react";

/**
 * Local Storage Hook
 * 本地存储 Hook - 支持类型安全的本地存储操作
 */

interface UseLocalStorageOptions<T> {
  serializer?: (value: T) => string;
  deserializer?: (value: string) => T;
}

/**
 * Custom hook for local storage with type safety
 * @param key - Storage key
 * @param initialValue - Initial value if key doesn't exist
 * @param options - Serialization options
 * @returns [value, setValue, removeValue]
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T,
  options: UseLocalStorageOptions<T> = {}
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  const {
    serializer = JSON.stringify,
    deserializer = JSON.parse,
  } = options;

  // Get initial value from localStorage or use provided initial value
  const getStoredValue = useCallback((): T => {
    if (typeof window === "undefined") {
      return initialValue;
    }

    try {
      const item = window.localStorage.getItem(key);
      return item ? deserializer(item) : initialValue;
    } catch (error) {
      console.warn(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  }, [key, initialValue, deserializer]);

  const [storedValue, setStoredValue] = useState<T>(getStoredValue);

  // Sync with localStorage on mount
  useEffect(() => {
    setStoredValue(getStoredValue());
  }, [getStoredValue]);

  // Set value in state and localStorage
  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      try {
        const valueToStore =
          value instanceof Function ? value(storedValue) : value;

        setStoredValue(valueToStore);

        if (typeof window !== "undefined") {
          window.localStorage.setItem(key, serializer(valueToStore));

          // Dispatch custom event for cross-tab sync
          window.dispatchEvent(
            new StorageEvent("storage", {
              key,
              newValue: serializer(valueToStore),
            })
          );
        }
      } catch (error) {
        console.warn(`Error setting localStorage key "${key}":`, error);
      }
    },
    [key, serializer, storedValue]
  );

  // Remove value from localStorage
  const removeValue = useCallback(() => {
    try {
      setStoredValue(initialValue);
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(key);
      }
    } catch (error) {
      console.warn(`Error removing localStorage key "${key}":`, error);
    }
  }, [key, initialValue]);

  // Listen for changes from other tabs/windows
  useEffect(() => {
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === key && event.newValue !== null) {
        try {
          setStoredValue(deserializer(event.newValue));
        } catch (error) {
          console.warn(`Error parsing storage event for key "${key}":`, error);
        }
      }
    };

    if (typeof window !== "undefined") {
      window.addEventListener("storage", handleStorageChange);
      return () => window.removeEventListener("storage", handleStorageChange);
    }
  }, [key, deserializer]);

  return [storedValue, setValue, removeValue];
}

/**
 * Hook for managing project-specific storage
 * 项目特定存储管理 Hook
 */
export function useProjectStorage<T>(
  projectId: string,
  key: string,
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  const storageKey = `sandbox_project_${projectId}_${key}`;
  return useLocalStorage(storageKey, initialValue);
}
