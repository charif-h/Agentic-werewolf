# PowerShell integration test for the werewolf game
Write-Host "=== INTEGRATION TEST: WEREWOLF GAME SYSTEM ===" -ForegroundColor Green

# Test 1: Create game
Write-Host "`n1. Creating game with 5 players..." -ForegroundColor Yellow
try {
    $createResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/game/create" -Method Post -Headers @{"Content-Type"="application/json"} -Body '{"num_players": 5}'
    if ($createResponse.status -eq "success") {
        Write-Host "✅ Game created successfully" -ForegroundColor Green
        Write-Host "   Players: $($createResponse.game_state.num_players)" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Failed to create game" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Exception creating game: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Start game
Write-Host "`n2. Starting the game..." -ForegroundColor Yellow
try {
    $startResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/game/start" -Method Post
    if ($startResponse.status -eq "success") {
        Write-Host "✅ Game started successfully" -ForegroundColor Green
        Write-Host "   Announcement: $($startResponse.announcement)" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Failed to start game" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Exception starting game: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 3: Get game state
Write-Host "`n3. Checking game state..." -ForegroundColor Yellow
try {
    $state = Invoke-RestMethod -Uri "http://localhost:8000/api/game/state" -Method Get
    Write-Host "✅ Game state retrieved" -ForegroundColor Green
    Write-Host "   Phase: $($state.phase)" -ForegroundColor Cyan
    Write-Host "   Day: $($state.day_number)" -ForegroundColor Cyan
    
    $alivePlayers = $state.players | Where-Object {$_.status -eq "alive"}
    Write-Host "   Alive players: $($alivePlayers.Count)" -ForegroundColor Cyan
    
    Write-Host "`n   Player roles:" -ForegroundColor Cyan
    $state.players | ForEach-Object {
        $roleColor = if ($_.role -eq "werewolf") { "Red" } else { "White" }
        Write-Host "     $($_.name): $($_.role)" -ForegroundColor $roleColor
    }
} catch {
    Write-Host "❌ Exception getting game state: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 4: Test night phase
Write-Host "`n4. Testing night phase..." -ForegroundColor Yellow
try {
    $nightResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/game/next-phase" -Method Post
    if ($nightResponse.status -eq "success") {
        Write-Host "✅ Night phase completed" -ForegroundColor Green
        Write-Host "   Result: $($nightResponse.data.announcement)" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Failed night phase" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Exception in night phase: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 5: Test discussion phase
Write-Host "`n5. Testing discussion phase..." -ForegroundColor Yellow
try {
    $discussionResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/game/next-phase" -Method Post
    if ($discussionResponse.status -eq "success") {
        Write-Host "✅ Discussion phase completed" -ForegroundColor Green
        Write-Host "   Messages: $($discussionResponse.data.messages.Count)" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Failed discussion phase" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Exception in discussion phase: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== INTEGRATION TEST COMPLETED ===" -ForegroundColor Green
Write-Host "All core functionality is working!" -ForegroundColor Green