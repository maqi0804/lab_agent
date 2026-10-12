import { getToken } from '@/utils/auth'
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/manager/home' },
    {
      path: '/manager',
      name: 'Layout',
      component: () => import('@/layouts/Layouts.vue'),
      children: [
        { path: 'home', name: 'Home', component: () => import('@/views/Home.vue') },
        { path: 'labs', name: 'Lab', component: () => import('@/views/Lab.vue') },
        { path: 'profile', name: 'Profile', component: () => import('@/views/Profile.vue') }
        // { path: 'devices', name: 'Device', component: () => import('@/views/Device.vue') },
        // { path: 'users', name: 'User', component: () => import('@/views/User.vue') }
      ]
    },
    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
    { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') }
  ]
})

//路由守卫，验证token是否存在，若不存在则跳转到登录页面
router.beforeEach((to, from) => {
  const token = getToken()
  if (to.path === '/login' || to.path === '/register') {
    return true
  } else {
    return token ? true : '/login'
  }
})

export default router
