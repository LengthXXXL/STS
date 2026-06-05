import { createRouter, createWebHistory } from 'vue-router'
import BuilderView from '../views/BuilderView.vue'
import ForumView from '../views/ForumView.vue'
import LoginView from '../views/LoginView.vue'
import PersonalSpaceView from '../views/PersonalSpaceView.vue'
import RegisterView from '../views/RegisterView.vue'
import SharedBlocksView from '../views/SharedBlocksView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'builder', component: BuilderView },
    { path: '/space', name: 'space', component: PersonalSpaceView },
    { path: '/forum', name: 'forum', component: ForumView },
    { path: '/blocks', name: 'shared-blocks', component: SharedBlocksView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: RegisterView }
  ]
})
