import random
import sys
import pygame
from buildings import REGISTRY

pygame.init()
N, CELL, LEFT, TOP = 12, 48, 20, 92
PX = LEFT + N * CELL + 24
W, H = PX + 310, TOP + N * CELL + 20
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption('Stop the Darkness - Prototype')
clock = pygame.time.Clock()
font = pygame.font.SysFont('arial', 17)
small = pygame.font.SysFont('arial', 13)
big = pygame.font.SysFont('arial', 22, bold=True)
COLORS = {'Field':(117,165,86),'Forest':(39,105,54),'Rocks':(125,125,132),'Mushroom Forest':(133,83,148),'Water':(68,145,204),'Stone Circle':(204,183,137),'Village':(192,151,92),'Mining Village':(153,129,109),'Magical Village':(177,112,195),'Docks':(169,135,91),'Treetop Village':(61,139,83)}
DARK, WHITE, GOLD = (32,34,40), (245,245,245), (255,210,65)

class Tile:
    def __init__(self, terrain='Field', building=None, level=1):
        self.terrain = terrain
        self.building = building or terrain
        self.level = level
        self.dark = False

def spiral_path():
    path, left, right, top, bottom = [], 0, N-1, 0, N-1
    while left <= right and top <= bottom:
        for y in range(top, bottom+1): path.append((left,y))
        left += 1
        for x in range(left, right+1): path.append((x,bottom))
        bottom -= 1
        if left <= right:
            for y in range(bottom, top-1, -1): path.append((right,y))
            right -= 1
        if top <= bottom:
            for x in range(right, left-1, -1): path.append((x,top))
            top += 1
    return path

SPIRAL = spiral_path()

def water_regions(positions):
    remaining = set(positions)
    regions = []
    while remaining:
        start = remaining.pop()
        region = {start}
        queue = [start]
        while queue:
            x, y = queue.pop()
            for neighbor in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    region.add(neighbor)
                    queue.append(neighbor)
        regions.append(region)
    return regions


def generate_layout():
    # Counts inferred from six observed standard maps.
    centers = [(5,5),(6,5),(5,6),(6,6)]
    all_cells = {(x,y) for y in range(N) for x in range(N)}
    stone = random.choice(centers)
    target_water = random.randint(30,33)
    target_forest = random.randint(41,44)
    target_lakes = random.randint(3,6)

    for attempt in range(700):
        water = set()
        # Grow separate pools, rather than scattering individual water tiles.
        sizes = [1] * target_lakes
        for _ in range(target_water-target_lakes):
            sizes[random.randrange(target_lakes)] += 1
        random.shuffle(sizes)
        valid = True
        for size in sizes:
            choices = list(all_cells - water - set(centers))
            random.shuffle(choices)
            placed = False
            for seed in choices:
                if any(abs(seed[0]-wx)+abs(seed[1]-wy)==1 for wx,wy in water):
                    continue
                pool = {seed}
                while len(pool) < size:
                    frontier = {(nx,ny) for px,py in pool
                                for nx,ny in ((px-1,py),(px+1,py),(px,py-1),(px,py+1))
                                if (nx,ny) in all_cells and (nx,ny) not in water
                                and (nx,ny) not in centers and (nx,ny) not in pool
                                and all(abs(nx-wx)+abs(ny-wy)>1 for wx,wy in water)}
                    if not frontier:
                        break
                    pool.add(random.choice(tuple(frontier)))
                if len(pool) == size:
                    water.update(pool)
                    placed = True
                    break
            if not placed:
                valid = False
                break
        if not valid or len(water) != target_water or len(water_regions(water)) != target_lakes:
            continue

        available = all_cells - water - {stone}
        crosses = [(x,y) for x in range(1,N-1) for y in range(1,N-1)
                   if {(x,y),(x-1,y),(x+1,y),(x,y-1),(x,y+1)} <= available]
        random.shuffle(crosses)
        if not crosses:
            continue
        first = crosses[0]
        def plus(c):
            x,y=c
            return {(x,y),(x-1,y),(x+1,y),(x,y-1),(x,y+1)}
        forest = plus(first)
        # A second guaranteed cluster is occasional, not every map.
        if random.random() < .28:
            other = next((c for c in crosses[1:] if len(plus(c) & forest)==0), None)
            if other is not None:
                forest.update(plus(other))
        if len(forest) > target_forest:
            continue
        # Grow forests into groups to resemble the reference map.
        while len(forest) < target_forest:
            candidates = list(available - forest)
            weights = [1 + 5*sum((nx,ny) in forest for nx,ny in
                       ((x-1,y),(x+1,y),(x,y-1),(x,y+1))) for x,y in candidates]
            forest.add(random.choices(candidates, weights=weights, k=1)[0])
        formed_crosses = sum(plus((cx,cy)) <= forest for cx in range(1,N-1) for cy in range(1,N-1))
        if formed_crosses > 2:
            continue
        free = list(available - forest)
        if len(free) < 19:
            continue
        rocks = set(random.sample(free,15))
        free = list(set(free)-rocks)
        # Guarantee a Mushroom Forest within 3 orthogonal tile steps of Stone Circle.
        nearby = [cell for cell in free if 0 < abs(cell[0]-stone[0]) + abs(cell[1]-stone[1]) <= 3]
        if not nearby:
            continue
        guaranteed_mushroom = random.choice(nearby)
        mushrooms = {guaranteed_mushroom}
        mushrooms.update(random.sample([cell for cell in free if cell != guaranteed_mushroom], 3))
        tiles = [[Tile() for _ in range(N)] for _ in range(N)]
        for positions, kind in ((water,'Water'),(forest,'Forest'),(rocks,'Rocks'),(mushrooms,'Mushroom Forest')):
            for x,y in positions:
                tiles[y][x] = Tile(kind)
        sx,sy=stone
        tiles[sy][sx] = Tile('Stone Circle')
        return tiles
    raise RuntimeError('Could not generate a map with the requested constraints')


def new_map():
    return generate_layout()

PRODUCTION = {('Forest',2):{'wood':3},('Forest',3):{'wood':5},('Forest',4):{'wood':10},('Rocks',2):{'rock':3},('Rocks',3):{'rock':7},('Rocks',4):{'rock':10},('Mushroom Forest',2):{'wood':1,'magic':2},('Treetop Village',1):{'wood':10,'magic':1},('Treetop Village',2):{'wood':20,'magic':2}}
# Temporary costs for testing; replace when the original costs are known.
COSTS = {'Forest':{2:{'wood':3},3:{'wood':8},4:{'wood':15}},'Rocks':{2:{'wood':3},3:{'wood':8},4:{'wood':15}},'Mushroom Forest':{2:{'wood':4}},'Stone Circle':{2:{'rock':100,'magic':100}}}
COLORS.update(REGISTRY.export_colors())
PRODUCTION.update(REGISTRY.export_production())
COSTS.update(REGISTRY.export_costs())
grid = new_map()
resources = {'wood':20.0,'rock':20.0,'magic':20.0}
dark_index, selected, won = 0, (5,5), False
playing = False
paused = False
pause_started = None
message = 'Map ready. Press Play to start darkness.'
last_dark, last_prod = pygame.time.get_ticks(), pygame.time.get_ticks()

def adjacent(x,y):
    for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
        if 0 <= nx < N and 0 <= ny < N: yield nx,ny

def can_upgrade_to_treetop_village(x,y):
    if grid[y][x].building != 'Forest':
        return False
    neighbors = list(adjacent(x,y))
    return len(neighbors) == 4 and all(grid[ny][nx].building in ('Forest', 'Treetop Village') for nx,ny in neighbors)

def production(tile,x,y):
    if tile.dark: return {}
    result = PRODUCTION.get((tile.building,tile.level), {}).copy()
    for resource, amount in list(result.items()):
        bonus = 0
        for nx,ny in adjacent(x,y):
            other = grid[ny][nx]
            if other.dark: continue
            if resource == 'wood' and other.building == 'Forest':
                bonus += .50 if other.level >= 4 else .25
            if resource == 'wood' and other.building == 'Treetop Village':
                bonus += .50 if other.level == 1 else 1.00
            if resource == 'rock' and other.building == 'Rocks' and other.level >= 4:
                bonus += .25
            bonus += REGISTRY.adjacency_bonus(resource, other.building, other.level)
        result[resource] = amount * (1 + bonus)
    return result

def afford(cost): return all(resources.get(k,0) >= v for k,v in cost.items())

def upgrade():
    global message, won, dark_index
    x,y = selected
    t = grid[y][x]
    if t.dark:
        message = 'Darkness disables this tile; its building remains.'
        return
    if t.building in ('Field', 'Water'):
        neighbors = [(grid[ny][nx].building, grid[ny][nx].level) for nx,ny in adjacent(x,y)]
        target = REGISTRY.target_for(t.building, neighbors)
        if not target:
            message = 'Nothing can be built here yet. Check adjacent areas.'
            return
        cost = REGISTRY.get(target).build_cost
        if not cost.can_afford(resources):
            message = f'Need {cost.text()}.'
            return
        cost.pay(resources)
        t.building, t.level = target, 1
        message = 'Built ' + target + '.'
        return
    if t.building == 'Stone Circle':
        if t.level >= 2:
            message = 'Stone Circle is already Level 2.'
            return
        cost = COSTS['Stone Circle'][2]
        if not afford(cost):
            message = 'Need 100 rock and 100 magic.'
            return
        resources['rock'] -= 100
        resources['magic'] -= 100
        t.level = 2
        for row in grid:
            for tile in row:
                tile.dark = False
        dark_index = len(SPIRAL)
        won, message = True, 'Victory! Stone Circle cleared all darkness. Darkness will not spread again.'
        return
    b = REGISTRY.get(t.building)
    if b:
        neighbors = [(grid[ny][nx].building, grid[ny][nx].level) for nx,ny in adjacent(x,y)]
        err = b.upgrade_error(t.level, neighbors, resources)
        if err:
            message = err
            return
        b.upgrade_cost(t.level).pay(resources)
        t.level += 1
        message = f'{b.display_name(t.level)} upgraded to Level {t.level}.'
        return
    max_level = 2 if t.building == 'Treetop Village' else 4 if t.building in ('Forest','Rocks') else 2
    if t.level >= max_level:
        message = 'This building is at max level.'
        return
    cost = COSTS.get(t.building,{}).get(t.level+1)
    if not cost:
        message = 'Upgrade cost not supplied.'
        return
    if not afford(cost):
        message = 'Not enough resources for temporary test cost.'
        return
    for k,v in cost.items(): resources[k] -= v
    if t.building == 'Forest' and t.level == 1 and can_upgrade_to_treetop_village(x,y):
        t.building, t.level = 'Treetop Village', 1
        message = 'Forest upgraded into Treetop Village Level 1!'
        return
    if t.building == 'Treetop Village' and t.level == 1:
        message = 'Treetop Village Level 2 upgrade cost is not supplied yet.'
        return
    t.level += 1
    message = f'{t.building} upgraded to Level {t.level}.'

REGEN_BUTTON = pygame.Rect(PX, 22, 150, 38)
PLAY_BUTTON = pygame.Rect(PX + 158, 22, 68, 38)
PAUSE_BUTTON = pygame.Rect(PX + 234, 22, 76, 38)

def draw_text(text,x,y,color=WHITE,f=font):
    screen.blit(f.render(text,True,color),(x,y))

def draw():
    screen.fill(DARK)
    draw_text('STOP THE DARKNESS - PROTOTYPE',LEFT,14,GOLD,big)
    draw_text('Click tiles to upgrade | Darkness: 5 sec/tile after Play',LEFT,49,WHITE,small)
    for y in range(N):
        for x in range(N):
            t=grid[y][x]
            rect=pygame.Rect(LEFT+x*CELL,TOP+y*CELL,CELL-2,CELL-2)
            c=COLORS.get(t.building,COLORS['Field'])
            if t.dark: c=tuple(int(v*.28) for v in c)
            pygame.draw.rect(screen,c,rect,border_radius=4)
            labels={'Stone Circle':'SC','Mushroom Forest':'MF','Mining Village':'MV','Magical Village':'MG','Treetop Village':'TV'}
            label=labels.get(t.building,t.building[:2].upper())
            screen.blit(small.render(label,True,WHITE),(rect.x+10,rect.y+5))
            if t.building not in ('Field','Water'):
                screen.blit(small.render('L'+str(t.level),True,WHITE),(rect.x+13,rect.y+25))
            if selected==(x,y): pygame.draw.rect(screen,GOLD,rect,3,border_radius=4)
            mx,my=pygame.mouse.get_pos()
            if rect.collidepoint(mx,my): pygame.draw.rect(screen,(255,255,255),rect,2,border_radius=4)
            number = y * N + x + 1
            number_surface = small.render(str(number), True, (20, 22, 25))
            number_bg = pygame.Rect(rect.right - number_surface.get_width() - 5, rect.bottom - 16, number_surface.get_width() + 4, 15)
            pygame.draw.rect(screen, (239, 235, 203), number_bg, border_radius=2)
            screen.blit(number_surface, (number_bg.x + 2, number_bg.y))
            if playing and not paused and dark_index < len(SPIRAL) and SPIRAL[dark_index] == (x,y): pygame.draw.circle(screen,(255,50,50),rect.center,6)
    x=PX
    pygame.draw.rect(screen,(76,112,93),REGEN_BUTTON,border_radius=6)
    pygame.draw.rect(screen,WHITE,REGEN_BUTTON,2,border_radius=6)
    draw_text('Regenerate',REGEN_BUTTON.x+18,REGEN_BUTTON.y+9,WHITE,font)
    pygame.draw.rect(screen,(53,130,85) if not playing and not won else (75,78,82),PLAY_BUTTON,border_radius=6)
    pygame.draw.rect(screen,WHITE,PLAY_BUTTON,2,border_radius=6)
    draw_text('Play',PLAY_BUTTON.x+17,PLAY_BUTTON.y+9,WHITE,font)
    pygame.draw.rect(screen,(155,105,52) if playing and not paused and not won else (75,78,82),PAUSE_BUTTON,border_radius=6)
    pygame.draw.rect(screen,WHITE,PAUSE_BUTTON,2,border_radius=6)
    draw_text('Pause',PAUSE_BUTTON.x+13,PAUSE_BUTTON.y+9,WHITE,font)
    if paused: draw_text('PAUSED',LEFT+290,14,GOLD,big)
    draw_text('Resources',x,TOP,GOLD,big)
    for i,k in enumerate(('wood','rock','magic')): draw_text(f'{k.title()}: {resources[k]:.1f}',x,TOP+38+i*28)
    mx,my=pygame.mouse.get_pos()
    hx,hy=(mx-LEFT)//CELL,(my-TOP)//CELL
    hovering=0<=hx<N and 0<=hy<N
    if hovering:
        t=grid[hy][hx]
        tx,ty=hx,hy
        heading='This area'
    else:
        tx,ty=selected
        t=grid[ty][tx]
        heading='Selected area'
    draw_text(heading,x,TOP+145,GOLD,big)
    draw_text(f'Position: ({tx};{ty})',x,TOP+178,WHITE,small)
    draw_text(t.building,x,TOP+202,WHITE,font)
    draw_text(f'Level {t.level}',x,TOP+226,WHITE,font)
    if t.dark:
        draw_text('Covered by darkness',x,TOP+302,(230,100,100),small)
    draw_text('Production per minute:',x,TOP+270,WHITE,font)
    prod=production(t,tx,ty)
    if prod:
        yy=TOP+302
        for k in ('wood','rock','magic'):
            if k in prod:
                draw_text(f'{k.title()}: {prod[k]:.2f}',x+8,yy,COLORS.get(t.building,WHITE),small); yy+=21
    else:
        draw_text('None',x+8,TOP+302,WHITE,small)
    bonuses=[]
    if t.building=='Forest':
        bonuses.append(f'Wood to adjacent: {50 if t.level>=4 else 25}%')
    if t.building=='Treetop Village':
        bonuses.append(f'Wood to adjacent: {50 if t.level == 1 else 100}%')
    if t.building=='Rocks' and t.level>=4:
        bonuses.append('Rock to adjacent: 25%')
    draw_text('Boost to adjacent:',x,TOP+365,WHITE,font)
    if bonuses:
        for i,b in enumerate(bonuses): draw_text(b,x+8,TOP+393+i*21,WHITE,small)
    else:
        draw_text('None',x+8,TOP+393,WHITE,small)
    draw_text('Status',x,TOP+440,GOLD,big)
    words=message.split(); line=''; yy=TOP+475
    for word in words:
        if len(line+' '+word)>35: draw_text(line,x,yy,WHITE,small); yy+=18; line=word
        else: line=(line+' '+word).strip()
    if line: draw_text(line,x,yy,WHITE,small)
    if won: draw_text('VICTORY!',x,H-35,GOLD,big)
    pygame.display.flip()

def reset():
    global grid,dark_index,selected,last_dark,won,message,playing,paused,pause_started
    global resources, last_prod
    grid=new_map(); dark_index=0; selected=(5,5); last_dark=pygame.time.get_ticks(); last_prod=last_dark; won=False; playing=False; paused=False; pause_started=None
    resources={'wood':20.0,'rock':20.0,'magic':20.0}
    message='New map ready. Press Play to start darkness.'

running=True
while running:
    now=pygame.time.get_ticks()
    if playing and not paused and not won and now-last_dark >= 5000:
        last_dark=now
        if dark_index < len(SPIRAL):
            x,y=SPIRAL[dark_index]; grid[y][x].dark=True; dark_index+=1
            if dark_index==len(SPIRAL) and not won: message='Game Over! Darkness covered the map.'
    if playing and not paused and not won and now-last_prod >= 1000:
        for y in range(N):
            for x in range(N):
                for k,v in production(grid[y][x],x,y).items(): resources[k]+=v/60
        last_prod=now
    for e in pygame.event.get():
        if e.type==pygame.QUIT: running=False
        elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
            if REGEN_BUTTON.collidepoint(e.pos):
                reset()
                continue
            if PLAY_BUTTON.collidepoint(e.pos):
                if not won and dark_index < len(SPIRAL):
                    now_click = pygame.time.get_ticks()
                    if not playing:
                        playing = True
                        paused = False
                        pause_started = None
                        last_dark = now_click
                        last_prod = now_click
                        message = 'Game started. Darkness and production are active.'
                    elif paused:
                        elapsed = now_click - pause_started
                        last_dark += elapsed
                        last_prod += elapsed
                        paused = False
                        pause_started = None
                        message = 'Game resumed.'
                continue
            if PAUSE_BUTTON.collidepoint(e.pos):
                if playing and not paused and not won:
                    paused = True
                    pause_started = pygame.time.get_ticks()
                    message = 'Paused. Darkness and resource production stopped.'
                continue
            mx,my=e.pos; gx=(mx-LEFT)//CELL; gy=(my-TOP)//CELL
            if 0<=gx<N and 0<=gy<N:
                selected=(gx,gy)
                upgrade()
        elif e.type==pygame.KEYDOWN:
            if e.key==pygame.K_ESCAPE: running=False
            elif e.key==pygame.K_u: upgrade()
            elif e.key==pygame.K_n: reset()
            elif e.key==pygame.K_SPACE and playing and not paused and not won:
                if dark_index<len(SPIRAL):
                    x,y=SPIRAL[dark_index]; grid[y][x].dark=True; dark_index+=1
            elif e.key==pygame.K_r:
                for k in resources: resources[k]+=100
                message='Added 100 of each resource.'
    draw()
    clock.tick(60)
pygame.quit()
sys.exit()
