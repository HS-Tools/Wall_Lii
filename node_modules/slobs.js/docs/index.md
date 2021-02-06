# Global





* * *

### messageHandler(slobs) 

Handler for Messages based off ID's

**Parameters**

**slobs**: `object`, object containing slobs information.The slobs object created with slobs(message).

**Fires**: event:streamStarted

**Fires**: event:streamEnded

**Fires**: event:recordStarted

**Fires**: event:recordEnded



## Class: Slobs



## Class: Slobs


### Slobs.getScenes() 

**Returns**: `Map`, Map of all scenes & sources.

**Example**:
```js
slobs.getScenes();
```

### Slobs.getStreamingStatus() 

**Returns**: `string`, live / offline

**Example**:
```js
slobs.getStreamingStatus();
```

### Slobs.getStreamUptime() 

**Returns**: `string`, Time formatted (hh:mm:ss) or 'offline'

**Example**:
```js
slobs.getStreamUptime();
```

### Slobs.getRecordingUptime() 

**Returns**: `string`, Time formatted (hh:mm:ss) or 'offline'

**Example**:
```js
slobs.getRecordingUptime();
```

### Slobs.toggleSource(sceneName, sourceName) 

**Parameters**

**sceneName**: `string`, Case sensitive name of the Scene the source belongs to.

**sourceName**: `string`, Case sensitive name of the Source we wish to toggle.


**Example**:
```js
slobs.toggleSource("Game Scene", "Webcam")
```

### Slobs.setActiveScene(sceneName) 

**Parameters**

**sceneName**: `string`, Case sensitive name of the Scene we wish to set as active.


**Example**:
```js
slobs.setActiveScene("Game Scene");
```

### Slobs.toggleRecording() 


**Example**:
```js
slobs.toggleRecording();
```

### Slobs.toggleStreaming() 


**Example**:
```js
slobs.toggleStreaming();
```

### Slobs.getConnected() 


**Example**:
```js
var connected = slobs.getConnection();
```



* * *










