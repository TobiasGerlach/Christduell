import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { DuelScreen } from "../screens/DuelScreen";
import { DuelsListScreen } from "../screens/DuelsListScreen";

export type RootStackParamList = {
  DuelsList: undefined;
  Duel: { duelId: number };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  return (
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="DuelsList" component={DuelsListScreen} options={{ title: "Christduell" }} />
        <Stack.Screen name="Duel" component={DuelScreen} options={{ title: "Duel" }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
