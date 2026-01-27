/**
 * Authentication hooks using React Query
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { signup, login, getProfile, updateProfile, UserProfile, SignupRequest, LoginRequest } from '../api';
import { setAuthToken, setUser, clearAuthToken, getUser, isAuthenticated } from '../auth';
import { toast } from 'sonner';

export const authKeys = {
  profile: ['auth', 'profile'] as const,
};

/**
 * Hook to get current user profile
 */
export function useAuth() {
  const user = getUser();
  const authenticated = isAuthenticated();
  
  const { data: profile, isLoading, error } = useQuery({
    queryKey: authKeys.profile,
    queryFn: getProfile,
    enabled: authenticated, // Only fetch if authenticated
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  return {
    user: profile || user,
    isLoading,
    isAuthenticated: authenticated && !!profile,
    error,
  };
}

/**
 * Hook for user signup
 */
export function useSignup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SignupRequest) => signup(request),
    onSuccess: (data) => {
      setAuthToken(data.access_token);
      setUser({
        id: data.user_id,
        email: data.email,
        name: data.name,
        is_active: true,
        is_admin: false,
        created_at: new Date().toISOString(),
      });
      queryClient.setQueryData(authKeys.profile, {
        id: data.user_id,
        email: data.email,
        name: data.name,
        is_active: true,
        is_admin: false,
        created_at: new Date().toISOString(),
      });
      toast.success('Account created successfully!');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Signup failed');
    },
  });
}

/**
 * Hook for user login
 */
export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: LoginRequest) => login(request),
    onSuccess: async (data) => {
      setAuthToken(data.access_token);
      // Fetch full profile
      const profile = await getProfile();
      setUser(profile);
      queryClient.setQueryData(authKeys.profile, profile);
      toast.success('Logged in successfully!');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Login failed');
    },
  });
}

/**
 * Hook for logout
 */
export function useLogout() {
  const queryClient = useQueryClient();

  return () => {
    clearAuthToken();
    queryClient.clear();
    queryClient.removeQueries();
    toast.success('Logged out');
  };
}

/**
 * Hook to update user profile
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name?: string) => updateProfile(name),
    onSuccess: (data) => {
      setUser(data);
      queryClient.setQueryData(authKeys.profile, data);
      toast.success('Profile updated');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update profile');
    },
  });
}
