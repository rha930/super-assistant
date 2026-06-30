<template>
  <div class="h-screen flex items-center justify-center app-bg app-text">
    <div class="w-full max-w-sm p-8 app-surface rounded-xl shadow-lg border app-border">
      <h1 class="text-2xl font-bold text-center mb-6">Super Agent</h1>
      <p class="text-sm app-text-muted text-center mb-6">Sign in to continue</p>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium mb-1">Username</label>
          <input
            id="username"
            v-model="username"
            type="text"
            autocomplete="username"
            required
            :disabled="loading"
            class="w-full px-3 py-2 border app-border rounded-lg text-sm app-surface app-text focus:outline-none focus:ring-2"
            style="--tw-ring-color: var(--color-accent);"
            placeholder="Enter your username"
          />
        </div>

        <div>
          <label for="password" class="block text-sm font-medium mb-1">Password</label>
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            :disabled="loading"
            class="w-full px-3 py-2 border app-border rounded-lg text-sm app-surface app-text focus:outline-none focus:ring-2"
            style="--tw-ring-color: var(--color-accent);"
            placeholder="Enter your password"
          />
        </div>

        <div v-if="loginError" class="text-sm text-red-600 dark:text-red-400">
          {{ loginError }}
        </div>

        <button
          type="submit"
          :disabled="loading || !username.trim() || !password"
          class="w-full px-4 py-2 btn-primary rounded-lg disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuthStore } from '../stores/authStore'

const authStore = useAuthStore()

const username = ref('')
const password = ref('')

const loading = computed(() => authStore.loading)
const loginError = computed(() => authStore.loginError)

const handleLogin = async () => {
  await authStore.login(username.value.trim(), password.value)
}
</script>
