local website = "" -- CHANGE TO YOUR DISCORD BOT'S HOSTING WEBSITE
-- dm @blinxo. on discord for help
local players = game:GetService("Players")
local replicatedStorage = game:GetService("ReplicatedStorage")
local httpService = game:GetService("HttpService")
local virtualUser = game:GetService("VirtualUser")
local textChatService = game:GetService("TextChatService")

local localPlayer = players.LocalPlayer
local playerGUI = localPlayer:WaitForChild("PlayerGui")

print("[Blinxo's Deposit Bot] Waiting for game to load...")
task.wait(5)

local tradingWindow = nil
local tradingMessage = nil
local tradingStatus = nil

pcall(function()
    tradingWindow = playerGUI:WaitForChild("TradeWindow", 10)
    tradingMessage = playerGUI:WaitForChild("Message", 10)
    tradingStatus = tradingWindow:WaitForChild("Frame"):WaitForChild("PlayerItems"):WaitForChild("Status")
end)

local tradingCommands = nil
pcall(function()
    local library = replicatedStorage:WaitForChild("Library", 10)
    tradingCommands = require(library:WaitForChild("Client"):WaitForChild("TradingCmds"))
end)

if not tradingCommands then
    print("[Blinxo's Deposit Bot] ERROR: Could not load trading commands!")
end

local httpRequest = nil
if request then
    httpRequest = request
elseif syn and syn.request then
    httpRequest = syn.request
elseif http and http.request then
    httpRequest = http.request
end

if not httpRequest then
    pcall(function() httpRequest = getrenv().request end)
end

print("[Blinxo's Deposit Bot] HTTP: " .. (httpRequest and "READY" or "NOT AVAILABLE"))

local tradeId = 0
local startTick = tick()
local tradeUser = nil
local goNext = true
local detectedItems = {}
local detectedGems = 0
local detectedUserId = 0

local hasSentReady = false
local hasConfirmed = false
local hasSentAPI = false
local currentTradeLocalId = 0

local function getTrades()
    if not tradingCommands then return {} end
    local trades = {}
    local success, functionTrades = pcall(function()
        return tradingCommands.GetAllRequests()
    end)
    if success and functionTrades then
        for player, trade in next, functionTrades do
            if trade and trade[localPlayer] then
                table.insert(trades, player)
            end
        end
    end
    return trades
end

local function getTradeId()
    if not tradingCommands then return 0 end
    local success, state = pcall(function()
        return tradingCommands.GetState()
    end)
    return (success and state and state._id) or 0
end

local function acceptTradeRequest(player)
    if not tradingCommands then return false end
    local success = pcall(function() tradingCommands.Request(player) end)
    return success
end

local function rejectTradeRequest(player)
    if not tradingCommands then return end
    pcall(function() tradingCommands.Reject(player) end)
end

local function readyTrade()
    if not tradingCommands then return end
    if hasSentReady then return end
    hasSentReady = true
    pcall(function() tradingCommands.SetReady(true) end)
    print("[Blinxo's Deposit Bot] Ready sent")
end

local function confirmTrade()
    if not tradingCommands then return end
    if hasConfirmed then return end
    hasConfirmed = true
    pcall(function() tradingCommands.SetConfirmed(true) end)
    print("[Blinxo's Deposit Bot] Confirm sent")
end

local function declineTrade()
    if not tradingCommands then return end
    pcall(function() tradingCommands.Decline() end)
end

local function sendMessage(msg)
    pcall(function()
        if textChatService and textChatService.TextChannels and textChatService.TextChannels.RBXGeneral then
            textChatService.TextChannels.RBXGeneral:SendAsync("Deposit | "..msg)
        end
    end)
    pcall(function()
        if tradingCommands then
            tradingCommands.Message("Deposit | "..msg)
        end
    end)
end

local assetIds = {}
local goldAssetids = {}
local nameAssetIds = {}

local directory = replicatedStorage:FindFirstChild("__DIRECTORY")
if directory then
    local petsFolder = directory:FindFirstChild("Pets")
    if petsFolder then
        local hugeFolder = petsFolder:FindFirstChild("Huge")
        if hugeFolder then
            for _, pet in next, hugeFolder:GetChildren() do
                local success, petData = pcall(require, pet)
                if success and petData then
                    table.insert(assetIds, petData.thumbnail)
                    table.insert(assetIds, petData.goldenThumbnail)
                    table.insert(goldAssetids, petData.goldenThumbnail)
                    table.insert(nameAssetIds, {
                        name = petData.name,
                        assetIds = {petData.thumbnail, petData.goldenThumbnail},
                        _id = petData._id
                    })
                end
            end
        end
        
        local titanicFolder = petsFolder:FindFirstChild("Titanic")
        if titanicFolder then
            for _, pet in next, titanicFolder:GetChildren() do
                local success, petData = pcall(require, pet)
                if success and petData then
                    table.insert(assetIds, petData.thumbnail)
                    table.insert(assetIds, petData.goldenThumbnail)
                    table.insert(goldAssetids, petData.goldenThumbnail)
                    table.insert(nameAssetIds, {
                        name = petData.name,
                        assetIds = {petData.thumbnail, petData.goldenThumbnail},
                        _id = petData._id
                    })
                end
            end
        end
        
        local gargantuanFolder = petsFolder:FindFirstChild("Gargantuan")
        if gargantuanFolder then
            for _, pet in next, gargantuanFolder:GetChildren() do
                local success, petData = pcall(require, pet)
                if success and petData then
                    table.insert(assetIds, petData.thumbnail)
                    table.insert(assetIds, petData.goldenThumbnail)
                    table.insert(goldAssetids, petData.goldenThumbnail)
                    table.insert(nameAssetIds, {
                        name = petData.name,
                        assetIds = {petData.thumbnail, petData.goldenThumbnail},
                        _id = petData._id
                    })
                end
            end
        end
    end
end

print("[Blinxo's Deposit Bot] Loaded " .. #nameAssetIds .. " pet types")

local function checkItems()
    if not tradingWindow then
        return true, "Trade window not ready"
    end
    
    local items = {}
    local itemTotal = 0
    local gemAmount = 0
    local onlyHugesTitanics = true
    
    local playerItems = nil
    pcall(function()
        playerItems = tradingWindow.Frame.PlayerItems.Items
    end)
    
    if not playerItems then
        return true, "Trade window not ready"
    end
    
    for _, item in next, playerItems:GetChildren() do
        if item.Name == "ItemSlot" then
            itemTotal = itemTotal + 1
            
            local icon = item:FindFirstChild("Icon")
            if not icon or not icon.Image then
                onlyHugesTitanics = false
                break
            end
            
            if not table.find(assetIds, icon.Image) then
                onlyHugesTitanics = false
                break
            end
            
            local petName = "Unknown"
            for _, petData in pairs(nameAssetIds) do
                if table.find(petData.assetIds, icon.Image) then
                    petName = petData.name
                    break
                end
            end
            
            local rarity = "Normal"
            if icon:FindFirstChild("RainbowGradient") then
                rarity = "Rainbow"
            elseif table.find(goldAssetids, icon.Image) then
                rarity = "Golden"
            end
            
            local shiny = (item:FindFirstChild("ShinePulse") ~= nil)
            local petstring = (shiny and "✨ " or "") .. ((rarity == "Golden" and "Golden ") or (rarity == "Rainbow" and "Rainbow ") or "") .. petName
            
            table.insert(items, petstring)
            print("[Blinxo's Deposit Bot] Pet: " .. petstring)
        end
    end
    
    local playerDiamonds = nil
    pcall(function()
        playerDiamonds = tradingWindow.Frame:FindFirstChild("PlayerDiamonds")
    end)
    
    if playerDiamonds then
        local textLabel = playerDiamonds:FindFirstChildWhichIsA("TextLabel")
        if textLabel and textLabel.Text then
            local cleanText = textLabel.Text:gsub("[^%d]", "")
            gemAmount = tonumber(cleanText) or 0
            if gemAmount > 0 then
                print("[Blinxo's Deposit Bot] Gems: " .. gemAmount)
            end
        end
    end
    
    if itemTotal == 0 and gemAmount == 0 then
        return true, "Please deposit pets or gems"
    elseif not onlyHugesTitanics then
        return true, "Please deposit only Huges/Titanics/Gargantuans"
    else
        return false, items, gemAmount
    end
end

local function sendDepositToAPI(userId, items, gems)
    if hasSentAPI then
        print("[Blinxo's Deposit Bot] API already sent for this trade")
        return true
    end
    
    if not httpRequest then
        print("[Blinxo's Deposit Bot] No HTTP function")
        return false
    end
    
    hasSentAPI = true
    
    local payload = httpService:JSONEncode({
        roblox_id = tostring(userId),
        pets = items,
        gems = gems or 0
    })
    
    print("[Blinxo's Deposit Bot] Sending deposit to API...")
    print("[Blinxo's Deposit Bot] User ID: " .. userId)
    print("[Blinxo's Deposit Bot] Items: " .. #items .. " pets")
    print("[Blinxo's Deposit Bot] Gems: " .. (gems or 0))
    
    local success, result = pcall(function()
        return httpRequest({
            Url = website .. "/api/deposit",
            Method = "POST",
            Headers = {["Content-Type"] = "application/json"},
            Body = payload
        })
    end)
    
    if success and result then
        local status = result.StatusCode or 200
        print("[Blinxo's Deposit Bot] API Status: " .. status)
        if status == 200 then
            print("[Blinxo's Deposit Bot] Deposit sent successfully!")
            return true
        end
    else
        print("[Blinxo's Deposit Bot] Failed: " .. tostring(result))
    end
    return false
end

pcall(function()
    localPlayer.Idled:Connect(function()
        pcall(function()
            virtualUser:Button2Down(Vector2.new(0,0), workspace.CurrentCamera.CFrame)
            task.wait(1)
            virtualUser:Button2Up(Vector2.new(0,0), workspace.CurrentCamera.CFrame)
        end)
    end)
end)

spawn(function()
    while task.wait(1) do
        tradeId = getTradeId()
    end
end)

local function connectMessage(localId, items, gems, userId)
    if not tradingMessage then
        return false
    end
    
    local messageConnection
    local hasProcessed = false
    
    messageConnection = tradingMessage:GetPropertyChangedSignal("Enabled"):Connect(function()
        if tradingMessage.Enabled and not hasProcessed then
            local text = tradingMessage.Frame.Contents.Desc.Text
            print("[Blinxo's Deposit Bot] Msg: " .. text)
            
            if text == "✅ Trade successfully completed!" or string.find(text, "successfully completed") or string.find(text, "Trade success") then
                hasProcessed = true
                print("[Blinxo's Deposit Bot] TRADE SUCCESSFUL!")
                sendMessage("Trade Completed! Processing...")
                
                if #items > 0 or gems > 0 then
                    local sent = sendDepositToAPI(userId, items, gems)
                    if sent then
                        sendMessage("Deposit credited! +" .. #items .. " pets, +" .. gems .. " gems")
                        print("[Blinxo's Deposit Bot] Deposit credited!")
                    else
                        sendMessage("Deposit failed! Contact staff.")
                        print("[Blinxo's Deposit Bot] Deposit failed!")
                    end
                end
                
                messageConnection:Disconnect()
                task.wait(1)
                pcall(function() tradingMessage.Enabled = false end)
                
                goNext = true
                hasSentReady = false
                hasConfirmed = false
                hasSentAPI = false
                currentTradeLocalId = 0
                return true
                
            elseif string.find(text, "cancelled") or string.find(text, "left the game") then
                hasProcessed = true
                print("[Blinxo's Deposit Bot] Trade was cancelled")
                messageConnection:Disconnect()
                task.wait(1)
                pcall(function() tradingMessage.Enabled = false end)
                
                goNext = true
                hasSentReady = false
                hasConfirmed = false
                hasSentAPI = false
                currentTradeLocalId = 0
                return false
            end
        end
    end)
    
    return true
end

local function connectStatus(localId, userId)
    if not tradingStatus then
        return
    end
    
    local statusConnection
    local hasProcessed = false
    
    statusConnection = tradingStatus:GetPropertyChangedSignal("Visible"):Connect(function()
        if tradeId == localId and not hasProcessed then
            if tradingStatus.Visible then
                hasProcessed = true
                
                local error, items, gems = checkItems()
                
                if error then
                    sendMessage(items)
                    goNext = true
                    hasSentReady = false
                    hasConfirmed = false
                    hasSentAPI = false
                    currentTradeLocalId = 0
                else
                    print("[Blinxo's Deposit Bot] Valid items detected!")
                    readyTrade()
                    task.wait(1)
                    confirmTrade()
                    connectMessage(localId, items, gems, userId)
                end
                
                statusConnection:Disconnect()
            end
        end
    end)
end

spawn(function()
    while task.wait(1) do
        if not tradingCommands then
            task.wait(5)
        else
            local incomingTrades = getTrades()
            
            if #incomingTrades > 0 and goNext then
                local trade = incomingTrades[1]
                local username = trade.Name
                
                local success, id = pcall(function()
                    return players:GetUserIdFromNameAsync(username)
                end)
                tradeUser = success and id or 0
                
                print("[Blinxo's Deposit Bot] Trade from: " .. username .. " (ID: " .. tradeUser .. ")")
                
                local accepted = acceptTradeRequest(trade)
                
                if not accepted then
                    rejectTradeRequest(trade)
                    goNext = true
                else
                    local localId = getTradeId()
                    tradeId = localId
                    currentTradeLocalId = localId
                    
                    print("[Blinxo's Deposit Bot] Trade accepted! ID: " .. localId)
                    sendMessage("Trade accepted! Add Huges/Titanics/Gargantuans or 10M+ gems")
                    
                    hasSentReady = false
                    hasConfirmed = false
                    hasSentAPI = false
                    
                    spawn(function()
                        task.wait(60)
                        if tradeId == localId and goNext == false then
                            print("[Blinxo's Deposit Bot] Trade timed out!")
                            sendMessage("Trade timed out!")
                            declineTrade()
                            goNext = true
                            hasSentReady = false
                            hasConfirmed = false
                            hasSentAPI = false
                        end
                    end)
                    
                    connectStatus(localId, tradeUser)
                    goNext = false
                end
            end
        end
    end
end)

print("========================================")
print("Blinxo's Deposit Bot LOADED!")
print("Website: " .. website)
print("HTTP: " .. (httpRequest and "READY" or "NOT AVAILABLE"))
print("Accepts: Huges, Titanics, Gargantuans, 10M+ gems")
print("========================================")
print("Loaded in " .. string.format("%.2f", tick() - startTick) .. "s")
