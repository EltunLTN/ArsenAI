import random, time, math

class Intersection:
    def __init__(self, name):
        self.name = name
        # hər istiqamət üçün maşın sayı
        self.queues = {"north": 0, "south": 0, "east": 0, "west": 0}
        self.green_dir = "north"
        self.green_timer = 0
        self.mode = "ai"  # və ya "fixed"
    
    def update_queues(self, hour):
        """Real Bakı trafik paterni ilə maşın sayını yenilə"""
        # Peak saatlar: 08:00-09:30, 17:30-19:00
        if 8 <= hour <= 9 or 17 <= hour <= 19:
            base = random.randint(15, 40)
        elif 12 <= hour <= 13:
            base = random.randint(8, 20)
        else:
            base = random.randint(1, 8)
        
        for d in self.queues:
            # hər istiqamət fərqli sıxlıqda
            factor = {"north": 1.2, "south": 0.8, "east": 1.5, "west": 0.6}
            change = random.randint(-2, 3)
            self.queues[d] = max(0, int(base * factor[d]) + change)
    
    def ai_decide(self):
        """Ən çox maşın olan istiqamətə yaşıl ver"""
        if self.green_timer > 0:
            self.green_timer -= 1
            return
        
        busiest = max(self.queues, key=self.queues.get)
        self.green_dir = busiest
        # maşın sayına proporsional müddət (min 10, max 60 san)
        count = self.queues[busiest]
        self.green_timer = max(10, min(60, count * 1.5))
    
    def fixed_decide(self):
        """Sabit 30 saniyə — köhnə sistem"""
        if self.green_timer > 0:
            self.green_timer -= 1
            return
        dirs = list(self.queues.keys())
        idx = dirs.index(self.green_dir)
        self.green_dir = dirs[(idx + 1) % 4]
        self.green_timer = 30
    
    def step(self):
        if self.mode == "ai":
            self.ai_decide()
        else:
            self.fixed_decide()
        
        # yaşıl olan istiqamətdən maşınlar keçir
        passed = min(self.queues[self.green_dir], 
                     random.randint(3, 7))
        self.queues[self.green_dir] = max(0, 
                     self.queues[self.green_dir] - passed)
        
        return {
            "name": self.name,
            "queues": self.queues.copy(),
            "green": self.green_dir,
            "timer": self.green_timer,
            "mode": self.mode,
            "total_waiting": sum(self.queues.values())
        }