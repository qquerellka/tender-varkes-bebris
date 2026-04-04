export type DemoUser = {
  id: string
  name: string
  organizationName: string
  role: string
  persona: string
}

export const demoUsers: DemoUser[] = [
  {
    id: 'demo_control_zero',
    name: 'Control',
    organizationName: 'No personalization',
    role: 'baseline',
    persona: 'Нулевая персонализация',
  },
  {
    id: 'user_0001',
    name: 'User 1',
    organizationName: 'Municipal Organization 1',
    role: 'manager',
    persona: 'Транспорт и офисные закупки',
  },
  {
    id: 'user_0006',
    name: 'User 6',
    organizationName: 'Municipal Organization 1',
    role: 'analyst',
    persona: 'IT-оборудование и сервисная поддержка',
  },
  {
    id: 'user_0017',
    name: 'User 17',
    organizationName: 'Municipal Organization 3',
    role: 'customer',
    persona: 'Офисная мебель и транспорт',
  },
  {
    id: 'user_0049',
    name: 'User 49',
    organizationName: 'Municipal Organization 7',
    role: 'manager',
    persona: 'Канцтовары и сервисные услуги',
  },
  {
    id: 'user_0057',
    name: 'User 57',
    organizationName: 'Municipal Organization 8',
    role: 'manager',
    persona: 'Сервисы и IT-инфраструктура',
  },
]
